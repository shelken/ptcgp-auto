# -*- coding: utf-8 -*-
"""
任务执行器模块

负责在指定设备上执行任务，包括账号切换、任务执行和状态更新。
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.hooks import HookContext
from ptcgp_auto_v2.core.task_base import Task, TaskRegistry, TaskResult
from ptcgp_auto_v2.core.task_plan_utils import (
    build_account_plan_cache,
    compute_next_run_for_instance,
)
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.infra.account_syncer import AccountSnapshot
from ptcgp_auto_v2.infra.page_detector import DEFAULT_TEMPLATE_THRESHOLD
from ptcgp_auto_v2.utils.common_handlers import build_common_handlers
from ptcgp_auto_v2.utils.log_source import resolve_log_device

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import TaskInstance

logger = logging.getLogger(__name__)


@dataclass
class ExecutorConfig:
    """执行器配置"""

    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 30.0  # 重试间隔（秒）
    recovery_delay: float = 5.0  # 恢复等待时间（秒）
    app_package: str = ""  # 应用包名（应从 settings 传入）
    template_threshold: float = DEFAULT_TEMPLATE_THRESHOLD  # 模板匹配阈值
    auto_scale_instance_prefix: str = ""  # 自动实例名前缀
    stop_event: Optional[threading.Event] = field(default=None)  # 停止事件

    def __post_init__(self):
        """初始化后处理"""
        from ptcgp_auto_v2.config.settings import get_settings

        settings = get_settings()
        if not self.app_package:
            self.app_package = settings.app_package
        if not self.template_threshold:
            self.template_threshold = settings.template_threshold
        if not self.auto_scale_instance_prefix:
            self.auto_scale_instance_prefix = settings.auto_scale_instance_prefix


@dataclass
class TaskInstanceSnapshot:
    """任务实例运行快照（纯数据对象）。"""

    id: Optional[int]
    account_id: int
    task_type: str
    status: str
    reset_type: str
    error_message: Optional[str]
    last_completed_at: Optional[datetime]
    schedule_anchor_at: Optional[datetime]
    last_duration_seconds: Optional[int]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_instance(cls, instance: "TaskInstance") -> "TaskInstanceSnapshot":
        """从数据库任务实例对象构造运行快照。"""
        if instance.id is None:
            raise RuntimeError("任务实例 ID 为空，无法构造快照")
        return cls(
            id=instance.id,
            account_id=instance.account_id,
            task_type=instance.task_type,
            status=instance.status,
            reset_type=instance.reset_type,
            error_message=instance.error_message,
            last_completed_at=instance.last_completed_at,
            schedule_anchor_at=instance.schedule_anchor_at,
            last_duration_seconds=instance.last_duration_seconds,
            next_run_at=instance.next_run_at,
            created_at=instance.created_at,
            updated_at=instance.updated_at,
        )


class BaseExecutor(ABC):
    """
    执行器基类

    提供账号切换、组件初始化等共享功能。
    """

    def __init__(
        self,
        device: Device,
        device_pool: DevicePool,
        config: Optional[ExecutorConfig] = None,
    ):
        """
        初始化执行器

        Args:
            device: 执行任务的设备
            device_pool: 设备池（用于归还设备）
            config: 执行器配置
        """
        self.device = device
        self.device_pool = device_pool
        self.config = config or ExecutorConfig()

        # 延迟初始化的组件（在 run 时创建）
        self._adb = None
        self._recognizer = None
        self._page_detector = None
        self._account_switcher = None
        self._account_syncer = None

    @contextmanager
    def _repository_scope(self):
        """为一次数据库动作提供统一的 Repository 工厂。"""
        with session_scope() as session:
            yield RepositoryFactory(session)

    # --- 基础设施与账号环境 -------------------------------------------------

    def _should_stop(self) -> bool:
        """检查是否应该停止执行"""
        return bool(self.config.stop_event and self.config.stop_event.is_set())

    def _init_components(self):
        """初始化基础设施组件"""
        from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
        from ptcgp_auto_v2.infra.account_syncer import AccountSyncer
        from ptcgp_auto_v2.infra.adb import AdbController
        from ptcgp_auto_v2.infra.ocr import OcrEngine
        from ptcgp_auto_v2.infra.page_detector import PageDetector
        from ptcgp_auto_v2.infra.template import TemplateMatcher

        self._adb = AdbController(self.device.address)
        if not self._adb.connect():
            raise RuntimeError(f"无法连接设备: {self.device.address}")
        ocr_engine = OcrEngine()
        template_matcher = TemplateMatcher(threshold=self.config.template_threshold)
        # 初始化时立即注入设备真实分辨率
        template_matcher.set_screen_width(self._adb.screen_width)

        self._recognizer = (ocr_engine, template_matcher)
        self._page_detector = PageDetector(
            adb=self._adb,
            ocr_engine=ocr_engine,
            template_matcher=template_matcher,
        )
        self._page_detector.load_base_pages(COMMON_PAGES)
        self._account_switcher = AccountSwitcher(self._adb)
        self._account_syncer = AccountSyncer(self._adb)

    def _sync_account_on_finish(self):
        """任务结束时同步账号 XML 到数据库（但不清理设备文件，以便后续任务复用）"""
        if self._account_syncer:
            try:
                # 仅同步账号信息（提取 XML -> DB）。
                # 不在这里清理环境，避免同账号后续任务重复冷启动。
                self._account_syncer.get_current_account()
                logger.debug("已同步设备账号 XML")
            except Exception as e:
                logger.warning(f"同步账号 XML 失败: {e}")

    def _cleanup(self):
        """清理资源"""
        self._sync_account_on_finish()
        if self._adb:
            self._adb.disconnect()
        self.device_pool.release(self.device)
        logger.debug(f"设备已归还: {self.device.address}")

    def _restart_app(self):
        """重启游戏应用"""
        assert self._adb is not None
        logger.debug("重启游戏应用...")
        self._adb.restart_app(self.config.app_package)
        time.sleep(self.config.recovery_delay)

    def _is_current_account(self, target_account: AccountSnapshot) -> bool:
        """
        检查设备当前是否已登录目标账号

        通过从设备提取账号 XML 并比较来确定当前登录的账号。
        同时会比较设备与数据库的 session_token_iat，如果设备更新则同步到数据库。
        """
        assert self._account_syncer is not None
        if target_account.id is None:
            return False

        current_account = self._account_syncer.get_current_account()
        if current_account:
            if current_account.id is not None:
                self.device.update_current_account(current_account.id)
            logger.debug(
                f"设备当前账号: {current_account.nickname or current_account.game_id}"
            )
            return current_account.id == target_account.id

        logger.warning("无法获取设备当前账号，将尝试切换")
        return False

    def _switch_account(self, target_account: AccountSnapshot) -> bool:
        """切换到目标账号。"""
        assert self._account_switcher is not None
        if target_account.id is None:
            logger.error("目标账号 ID 为空，无法切换")
            return False

        logger.info(f"切换账号: {target_account.nickname} (ID: {target_account.id})")
        try:
            success = self._account_switcher.switch_to(target_account)
            if success:
                self.device.update_current_account(target_account.id)
                self._restart_app()
            return success
        except RuntimeError as e:
            logger.error(f"账号切换失败: {e}")
            return False

    def _ensure_target_account(self, target_account: AccountSnapshot) -> bool:
        """确保设备当前已经切换到目标账号。"""
        if self._is_current_account(target_account):
            return True
        return self._switch_account(target_account)

    def _resolve_log_nickname(self, account: AccountSnapshot) -> str:
        """统一解析日志中的账号显示名。"""
        nickname = account.nickname
        if nickname and nickname.lower() == "skn" and account.id is not None:
            return f"skn{account.id}"
        return nickname or account.display_name or str(account.id)

    @contextmanager
    def _bind_log_context(
        self,
        account: AccountSnapshot,
        initial_task: str = "",
    ):
        """统一绑定执行器级日志上下文。"""
        from ptcgp_auto_v2.utils.logger import clear_context, set_context

        device_display, color_key = resolve_log_device(
            self.device.address,
            self.config.auto_scale_instance_prefix,
        )
        set_context(
            device=device_display,
            nickname=self._resolve_log_nickname(account),
            task=initial_task,
            color_key=color_key,
        )
        try:
            yield
        finally:
            clear_context()

    # --- 任务构建 ---------------------------------------------------------

    def _build_task(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
    ) -> Task:
        """构建一个已注入上下文的任务对象。"""
        assert self._page_detector is not None
        assert self._adb is not None

        task_class = TaskRegistry.get(task_instance.task_type)
        self._page_detector.load_task_pages(task_class.pages)
        task = task_class(
            adb=self._adb,
            recognizer=self._recognizer,
            page_detector=self._page_detector,
        )
        task.register_handlers(build_common_handlers(self._adb, self._page_detector))
        task.bind_account(account)
        task.set_hook_context(self._build_hook_context(task, account))
        if self.config.stop_event:
            task.set_stop_event(self.config.stop_event)
        return task

    def _build_hook_context(self, task: Task, account: AccountSnapshot) -> HookContext:
        """构建 Hook 上下文"""
        return HookContext(
            device=self.device,
            account=account,
            task=task,
            executor=self,
        )

    def _get_or_create_task_instance(
        self, account_id: int, task_type: str
    ) -> Optional[TaskInstanceSnapshot]:
        """获取或创建任务实例（用于 Hook 插入任务）"""
        task_class = TaskRegistry.get_or_none(task_type)
        if not task_class:
            logger.warning(f"未知的任务类型: {task_type}")
            return None

        with self._repository_scope() as repos:
            instance = repos.task_instances().get_or_create(
                account_id=account_id,
                task_type=task_type,
                reset_type=task_class.reset_type.value,
            )
            return TaskInstanceSnapshot.from_instance(instance)

    def _unblock_dependent_tasks(self, account: AccountSnapshot):
        """恢复该账号被阻塞的任务"""
        if account.id is None:
            return
        with self._repository_scope() as repos:
            repo = repos.task_instances()
            blocked_tasks = repo.get_blocked_by_account(account.id)
            for task in blocked_tasks:
                if task.id is None:
                    raise RuntimeError("被阻塞任务缺少 ID，无法恢复")
                logger.info(
                    f"恢复被阻塞任务: {task.task_type} (账号: {account.display_name})"
                )
                repo.update_runtime_state(
                    task.id,
                    status=TaskStatus.PENDING.value,
                    next_run_at=None,
                )

    # --- 状态与结果收口 ---------------------------------------------------

    def _apply_task_status(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
        status: TaskStatus,
        error_message: Optional[str] = None,
        clear_error_on_success: bool = True,
        duration_seconds: Optional[int] = None,
        preserve_last_completed_at: bool = False,
    ):
        """更新任务实例状态"""
        if task_instance.id is None:
            raise RuntimeError("任务实例 ID 为空，无法更新状态")

        task_instance.status = status.value
        update_kwargs: dict[str, object] = {"status": status.value}
        if status == TaskStatus.COMPLETED:
            completed_at = datetime.now()
            task_instance.schedule_anchor_at = completed_at
            update_kwargs["schedule_anchor_at"] = completed_at
            if not preserve_last_completed_at:
                task_instance.last_completed_at = completed_at
                update_kwargs["last_completed_at"] = completed_at
            next_run_at = None
            if account.id is not None:
                with self._repository_scope() as repos:
                    fresh_account = repos.accounts().get_by_id(account.id)
                    if fresh_account is not None:
                        account_cache = build_account_plan_cache(fresh_account)
                        next_run_at, _, _, _ = compute_next_run_for_instance(
                            task_instance,
                            account_cache,
                        )
            task_instance.next_run_at = next_run_at
            update_kwargs["next_run_at"] = next_run_at
            # 恢复被阻塞的任务（前置任务完成后）
            self._unblock_dependent_tasks(account)
        if (
            status
            in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.SKIPPED,
                TaskStatus.BLOCKED,
            )
            and duration_seconds is not None
        ):
            task_instance.last_duration_seconds = max(0, duration_seconds)
            update_kwargs["last_duration_seconds"] = max(0, duration_seconds)
        if error_message is not None:
            task_instance.error_message = error_message
            update_kwargs["error_message"] = error_message
        elif clear_error_on_success and status == TaskStatus.COMPLETED:
            task_instance.error_message = None
            update_kwargs["error_message"] = None
        task_instance.updated_at = datetime.now()
        with self._repository_scope() as repos:
            repos.task_instances().update_runtime_state(task_instance.id, **update_kwargs)

        # 发送任务状态通知
        if status in (TaskStatus.FAILED, TaskStatus.BLOCKED):
            self._notify_task_status(task_instance, status.value, error_message or "")

    def _apply_task_failure(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
        error_message: Optional[str],
        *,
        duration_seconds: int = 0,
    ):
        """以失败状态结束任务实例。"""
        self._apply_task_status(
            task_instance=task_instance,
            account=account,
            status=TaskStatus.FAILED,
            error_message=error_message,
            clear_error_on_success=False,
            duration_seconds=duration_seconds,
        )

    def _apply_task_result(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
        result: TaskResult,
    ):
        """将 TaskResult 收敛成任务实例的最终状态。"""
        duration_seconds = self._get_result_duration_seconds(result)
        if result.success:
            if result.skipped:
                logger.info(
                    f"任务跳过: {task_instance.task_type} ({result.skip_reason})"
                )
                self._apply_task_status(
                    task_instance=task_instance,
                    account=account,
                    status=TaskStatus.SKIPPED,
                    error_message=f"跳过: {result.skip_reason}",
                    clear_error_on_success=False,
                    duration_seconds=duration_seconds,
                )
                return

            if self._handle_requeue_in_result(result, task_instance):
                return

            complete_reason = result.data.get("complete_reason")
            if complete_reason:
                logger.info(f"任务完成: {task_instance.task_type} ({complete_reason})")
                self._apply_task_status(
                    task_instance=task_instance,
                    account=account,
                    status=TaskStatus.COMPLETED,
                    error_message=f"完成: {complete_reason}",
                    clear_error_on_success=False,
                    duration_seconds=duration_seconds,
                    preserve_last_completed_at=result.preserve_last_completed_at,
                )
                return

            logger.info(f"任务完成: {task_instance.task_type}")
            self._apply_task_status(
                task_instance=task_instance,
                account=account,
                status=TaskStatus.COMPLETED,
                clear_error_on_success=True,
                duration_seconds=duration_seconds,
                preserve_last_completed_at=result.preserve_last_completed_at,
            )
            return

        logger.error(f"任务失败: {task_instance.task_type} - {result.error}")
        self._apply_task_failure(
            task_instance=task_instance,
            account=account,
            error_message=result.error,
            duration_seconds=duration_seconds,
        )

    def _measure_elapsed_seconds(self, started_monotonic: float) -> int:
        """将单调时钟差值转换为整数秒。"""
        elapsed_seconds = time.monotonic() - started_monotonic
        return max(0, int(elapsed_seconds + 0.5))

    def _get_result_duration_seconds(self, result: TaskResult) -> int:
        """从任务结果中读取耗时秒数。"""
        duration_seconds = result.data.get("duration_seconds")
        if isinstance(duration_seconds, int) and duration_seconds >= 0:
            return duration_seconds
        return 0

    def _set_result_duration_seconds(
        self,
        result: TaskResult,
        duration_seconds: int,
    ) -> TaskResult:
        """回填任务结果中的耗时秒数。"""
        result.data["duration_seconds"] = max(0, duration_seconds)
        return result

    def _execute_task_once(
        self,
        task: Task,
        *,
        skip_pre_hooks: bool = False,
    ) -> TaskResult:
        """执行单次任务并记录当前任务自身耗时。"""
        started_monotonic = time.monotonic()
        result = task.execute(skip_pre_hooks=skip_pre_hooks)
        duration_seconds = self._measure_elapsed_seconds(started_monotonic)
        return self._set_result_duration_seconds(result, duration_seconds)

    def _notify_task_status(
        self,
        task_instance: TaskInstanceSnapshot,
        status: str,
        message: str,
    ):
        """发送任务状态通知"""
        try:
            from ptcgp_auto_v2.infra.notifier import get_notifier

            notifier = get_notifier()
            notifier.notify_task_status(task_instance, status, message)
        except Exception as e:
            logger.warning(f"发送任务状态通知失败: {e}")

    def _reschedule_task(
        self,
        task_instance: TaskInstanceSnapshot,
        when: datetime,
        reason: Optional[str] = None,
    ):
        """将任务重新排队到指定时间执行（通用机制）。"""
        if task_instance.id is None:
            raise RuntimeError("任务实例 ID 为空，无法重排")
        task_instance.status = TaskStatus.PENDING.value
        task_instance.next_run_at = when
        update_kwargs: dict[str, object] = {
            "status": TaskStatus.PENDING.value,
            "next_run_at": when,
        }
        if reason:
            task_instance.error_message = f"等待复查: {reason}"
            update_kwargs["error_message"] = f"等待复查: {reason}"
        task_instance.updated_at = datetime.now()
        with self._repository_scope() as repos:
            repos.task_instances().update_runtime_state(task_instance.id, **update_kwargs)

    def _handle_requeue_in_result(
        self,
        result: "TaskResult",
        task_instance: TaskInstanceSnapshot,
    ) -> bool:
        """处理结果中的重排请求，返回是否已处理。"""
        requeue_at = result.data.get("requeue_at")
        if isinstance(requeue_at, datetime):
            complete_reason = result.data.get("requeue_reason") or result.data.get(
                "complete_reason"
            )
            self._reschedule_task(
                task_instance=task_instance,
                when=requeue_at,
                reason=complete_reason,
            )
            logger.info("任务重排: %s -> %s", task_instance.task_type, requeue_at)
            return True
        return False

    # --- 前置任务链执行 ---------------------------------------------------

    def _build_failed_result(
        self,
        error_message: str,
        duration_seconds: int,
    ) -> TaskResult:
        """构建一个带有耗时信息的失败结果。"""
        return self._set_result_duration_seconds(
            TaskResult.fail(error_message),
            duration_seconds,
        )

    def _extract_prerequisite_task_types(self, result: TaskResult) -> list[str]:
        """从任务结果中提取需要补跑的前置任务列表。"""
        pre_task_types = result.data.get("pre_task_types")
        if result.skipped and isinstance(pre_task_types, list) and pre_task_types:
            return pre_task_types
        return []

    def _apply_prerequisite_result(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
        result: TaskResult,
    ):
        """前置任务链有自己的收口规则，不在这里处理 requeue。"""
        duration_seconds = self._get_result_duration_seconds(result)
        if not result.success:
            self._apply_task_failure(
                task_instance=task_instance,
                account=account,
                error_message=result.error,
                duration_seconds=duration_seconds,
            )
            return

        self._apply_task_status(
            task_instance=task_instance,
            account=account,
            status=TaskStatus.SKIPPED if result.skipped else TaskStatus.COMPLETED,
            error_message=f"跳过: {result.skip_reason}" if result.skipped else None,
            clear_error_on_success=not result.skipped,
            duration_seconds=duration_seconds,
            preserve_last_completed_at=result.preserve_last_completed_at,
        )

    def _run_prerequisite_tasks(
        self,
        current_task_type: str,
        prerequisite_task_types: list[str],
        account: AccountSnapshot,
        current_duration_seconds: int,
        stack: set[str],
        chain: list[str],
    ) -> Optional[TaskResult]:
        """顺序执行当前任务收集到的前置任务。"""
        from ptcgp_auto_v2.utils.logger import set_context

        assert account.id is not None

        logger.debug(
            "任务 %s 收集到前置任务: %s",
            current_task_type,
            " -> ".join(prerequisite_task_types),
        )
        for pre_task_type in prerequisite_task_types:
            set_context(task=pre_task_type)
            pre_task_instance = self._get_or_create_task_instance(
                account_id=account.id,
                task_type=pre_task_type,
            )
            if pre_task_instance is None:
                return self._build_failed_result(
                    f"前置任务创建失败: {pre_task_type}",
                    current_duration_seconds,
                )

            logger.info(f"执行前置任务: {pre_task_type} (账号: {account.nickname})")
            pre_result = self._execute_task_with_prerequisites(
                pre_task_instance,
                account,
                stack,
                chain,
            )
            self._apply_prerequisite_result(pre_task_instance, account, pre_result)
            if not pre_result.success:
                return self._build_failed_result(
                    f"前置任务失败: {pre_result.error}",
                    current_duration_seconds,
                )

            set_context(task=current_task_type)

        return None

    def _resume_task_after_prerequisites(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
        initial_result: TaskResult,
        prerequisite_task_types: list[str],
        stack: set[str],
        chain: list[str],
    ) -> TaskResult:
        """执行完前置任务后，重新进入当前主任务。"""
        current_duration_seconds = self._get_result_duration_seconds(initial_result)
        failure_result = self._run_prerequisite_tasks(
            current_task_type=task_instance.task_type,
            prerequisite_task_types=prerequisite_task_types,
            account=account,
            current_duration_seconds=current_duration_seconds,
            stack=stack,
            chain=chain,
        )
        if failure_result is not None:
            return failure_result

        resumed_result = self._execute_task_once(
            self._build_task(task_instance, account),
            skip_pre_hooks=True,
        )
        total_duration_seconds = (
            current_duration_seconds + self._get_result_duration_seconds(resumed_result)
        )
        return self._set_result_duration_seconds(
            resumed_result,
            total_duration_seconds,
        )

    def _execute_task_with_prerequisites(
        self,
        task_instance: TaskInstanceSnapshot,
        account: AccountSnapshot,
        stack: Optional[set[str]] = None,
        chain: Optional[list[str]] = None,
    ) -> TaskResult:
        """执行任务：递归处理前置任务，并补齐前置任务自己的 pre/post hooks。"""
        from ptcgp_auto_v2.utils.logger import set_context

        if account.id is None:
            return TaskResult.fail("前置任务参数无效")

        # 使用显式的执行栈防止前置任务链出现循环依赖。
        stack = stack or set()
        chain = chain or []
        current_task_type = task_instance.task_type
        if current_task_type in stack:
            return TaskResult.fail(f"检测到前置任务循环: {current_task_type}")

        stack.add(current_task_type)
        chain.append(current_task_type)
        set_context(task=current_task_type)
        logger.debug("任务链: %s", " -> ".join(chain))
        try:
            initial_result = self._execute_task_once(
                self._build_task(task_instance, account)
            )
            prerequisite_task_types = self._extract_prerequisite_task_types(
                initial_result
            )
            if not prerequisite_task_types:
                return initial_result

            return self._resume_task_after_prerequisites(
                task_instance=task_instance,
                account=account,
                initial_result=initial_result,
                prerequisite_task_types=prerequisite_task_types,
                stack=stack,
                chain=chain,
            )
        finally:
            stack.remove(current_task_type)
            chain.pop()
            restored_task_type = chain[-1] if chain else current_task_type
            set_context(task=restored_task_type)

    @abstractmethod
    def run(self):
        """执行任务（子类实现）"""
        pass


class AccountExecutor(BaseExecutor):
    """
    账号任务执行器

    在一个设备上顺序执行同一账号的任务列表。
    单任务场景也统一收敛为长度为 1 的任务列表。
    """

    def __init__(
        self,
        device: Device,
        account: AccountSnapshot,
        task_instances: list[TaskInstanceSnapshot],
        device_pool: DevicePool,
        config: Optional[ExecutorConfig] = None,
    ):
        """
        初始化账号任务执行器

        Args:
            device: 执行任务的设备
            account: 账号
            task_instances: 按顺序排列的任务实例列表
            device_pool: 设备池（用于归还设备）
            config: 执行器配置
        """
        super().__init__(device, device_pool, config)
        self.account = account
        self.task_instances = task_instances
        self.pending_tasks = list(task_instances)

    def _fail_tasks(self, error_message: str, only_running: bool = False):
        """统一标记任务失败。"""
        for task_instance in self.task_instances:
            if only_running and task_instance.status != TaskStatus.RUNNING.value:
                continue
            self._apply_task_failure(
                task_instance=task_instance,
                account=self.account,
                error_message=error_message,
                duration_seconds=0,
            )

    def _prepare_run(self) -> bool:
        """初始化执行环境，并切换到目标账号。"""
        self._init_components()
        if self._should_stop():
            logger.info("收到停止信号，取消执行")
            return False

        if self._ensure_target_account(self.account):
            return True

        self._fail_tasks("账号切换失败")
        logger.error("账号切换失败，终止账号任务执行")
        return False

    def _should_skip_task(self, task_instance: TaskInstanceSnapshot) -> bool:
        """判断当前任务是否应直接跳过。"""
        if task_instance.status != TaskStatus.BLOCKED.value:
            return False

        logger.info(
            f"跳过被阻塞任务: {task_instance.task_type} (账号: {self.account.display_name})"
        )
        return True

    def _set_active_task(self, task_instance: TaskInstanceSnapshot):
        """切换当前任务上下文。"""
        from ptcgp_auto_v2.utils.logger import set_context

        set_context(task=task_instance.task_type)

    def _execute_single_task(self, task_instance: TaskInstanceSnapshot):
        """执行单个任务，并将结果收口到统一状态更新入口。"""
        self._set_active_task(task_instance)
        logger.info(f"执行任务: {task_instance.task_type}")
        try:
            result = self._execute_task_with_prerequisites(
                task_instance=task_instance,
                account=self.account,
            )
            self._apply_task_result(task_instance, self.account, result)
        except Exception as e:
            logger.exception(f"任务执行异常: {task_instance.task_type} - {e}")
            self._apply_task_failure(task_instance, self.account, str(e))

    def _run_pending_tasks(self):
        """顺序执行任务列表。"""
        index = 0
        while index < len(self.pending_tasks):
            task_instance = self.pending_tasks[index]
            if self._should_stop():
                logger.info("收到停止信号，中断任务执行")
                # 剩余任务保持 running 状态，重启后会被重置为 pending
                break

            if self._should_skip_task(task_instance):
                index += 1
                continue

            self._execute_single_task(task_instance)
            index += 1

    def run(self):
        """
        执行账号的所有任务

        按顺序执行所有任务，单个任务失败不影响后续任务执行。
        """
        task_types = [t.task_type for t in self.task_instances]
        initial_task = task_types[0] if task_types else ""
        with self._bind_log_context(self.account, initial_task=initial_task):
            logger.info(f"开始执行 {len(self.task_instances)} 个任务: {task_types}")
            try:
                if not self._prepare_run():
                    return
                self._run_pending_tasks()
                logger.info(f"账号任务执行完成 (账号: {self.account.display_name})")
            except Exception as e:
                logger.exception(f"账号执行器异常: {e}")
                self._fail_tasks(str(e), only_running=True)
            finally:
                self._cleanup()
