# -*- coding: utf-8 -*-
"""
任务执行器模块

负责在指定设备上执行任务，包括账号切换、任务执行和状态更新。
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.task_base import Task, TaskRegistry, TaskResult, TaskStatus
from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.utils.common_handlers import build_common_handlers
from ptcgp_auto_v2.infra.page_detector import DEFAULT_TEMPLATE_THRESHOLD

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account, TaskInstance

logger = logging.getLogger(__name__)


@dataclass
class ExecutorConfig:
    """执行器配置"""

    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 30.0  # 重试间隔（秒）
    recovery_delay: float = 5.0  # 恢复等待时间（秒）
    app_package: str = ""  # 应用包名（应从 settings 传入）
    template_threshold: float = DEFAULT_TEMPLATE_THRESHOLD  # 模板匹配阈值
    stop_event: Optional[threading.Event] = field(default=None)  # 停止事件

    def __post_init__(self):
        """初始化后处理"""
        from ptcgp_auto_v2.config.settings import get_settings

        settings = get_settings()
        if not self.app_package:
            self.app_package = settings.app_package
        if not self.template_threshold:
            self.template_threshold = settings.template_threshold


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

    def _should_stop(self) -> bool:
        """检查是否应该停止执行"""
        if self.config.stop_event and self.config.stop_event.is_set():
            return True
        return False

    def _init_components(self):
        """初始化基础设施组件"""
        from ptcgp_auto_v2.infra.adb import AdbController
        from ptcgp_auto_v2.infra.ocr import OcrEngine
        from ptcgp_auto_v2.infra.template import TemplateMatcher
        from ptcgp_auto_v2.infra.page_detector import PageDetector
        from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
        from ptcgp_auto_v2.infra.account_syncer import AccountSyncer

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

    def _build_task(self, task_instance: "TaskInstance", account: "Account") -> Task:
        assert self._page_detector is not None
        assert self._adb is not None

        task_class = TaskRegistry.get(task_instance.task_type)
        self._page_detector.load_task_pages(task_class.pages)
        task = task_class(
            adb=self._adb,
            recognizer=self._recognizer,
            page_detector=self._page_detector,
        )
        task.register_handlers(
            build_common_handlers(self._adb, self._page_detector)
        )
        task.bind_account(account)
        if self.config.stop_event:
            task.set_stop_event(self.config.stop_event)
        return task

    def _is_current_account(self, target_account: "Account") -> bool:
        """
        检查设备当前是否已登录目标账号

        通过从设备提取账号 XML 并比较来确定当前登录的账号。
        同时会比较设备与数据库的 session_token_iat，如果设备更新则同步到数据库。

        Args:
            target_account: 目标账号

        Returns:
            True 表示当前已登录目标账号
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

    def _switch_account(self, target_account: "Account") -> bool:
        """
        切换到目标账号

        Args:
            target_account: 目标账号

        Returns:
            True 表示切换成功
        """
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

    def _restart_app(self):
        """重启游戏应用"""
        assert self._adb is not None
        logger.debug("重启游戏应用...")
        self._adb.restart_app(self.config.app_package)
        time.sleep(self.config.recovery_delay)

    def _try_recover(self):
        """尝试恢复到可执行状态"""
        logger.debug("尝试恢复执行状态...")
        self._restart_app()

    def _unblock_dependent_tasks(self, account: "Account"):
        """恢复该账号被阻塞的任务"""
        if account.id is None:
            return

        from ptcgp_auto_v2.db.repositories import TaskInstanceRepository

        repo = TaskInstanceRepository()
        blocked_tasks = repo.get_blocked_by_account(account.id)
        for task in blocked_tasks:
            logger.info(
                f"恢复被阻塞任务: {task.task_type} (账号: {account.nickname})"
            )
            task.status = TaskStatus.PENDING.value
            task.save()

    def _sync_account_on_finish(self):
        """任务结束时同步账号 XML 到数据库（但不清理设备文件，以便后续任务复用）"""
        if self._account_syncer:
            try:
                # 仅同步账号信息（提取 XML -> DB）
                # 注意：我们不再这里调用 clean_device_xml 或 reset_game_environment
                # 这样如果下一个任务是同一个账号，就可以直接复用环境而不必重启
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

    def _apply_task_status(
        self,
        task_instance: "TaskInstance",
        account: "Account",
        status: TaskStatus,
        error_message: Optional[str] = None,
        clear_error_on_success: bool = True,
    ):
        """更新任务实例状态"""
        task_instance.status = status.value
        if status == TaskStatus.COMPLETED:
            task_instance.last_completed_at = datetime.now()
            # 恢复被阻塞的任务（前置任务完成后）
            self._unblock_dependent_tasks(account)
            if clear_error_on_success:
                task_instance.error_message = None
        if error_message:
            task_instance.error_message = error_message
        task_instance.updated_at = datetime.now()
        # 保存到数据库
        task_instance.save()

    @abstractmethod
    def run(self):
        """执行任务（子类实现）"""
        pass


class TaskExecutor(BaseExecutor):
    """
    任务执行器

    绑定到一个设备，执行分配的任务。
    职责：
    1. 账号切换（如需要）
    2. 任务执行（目标驱动 + 页面响应）
    3. 状态更新（任务实例状态）
    4. 错误处理和重试
    """

    def __init__(
        self,
        device: Device,
        task_instance: "TaskInstance",
        device_pool: DevicePool,
        config: Optional[ExecutorConfig] = None,
    ):
        """
        初始化执行器

        Args:
            device: 执行任务的设备
            task_instance: 任务实例
            device_pool: 设备池（用于归还设备）
            config: 执行器配置
        """
        super().__init__(device, device_pool, config)
        self.task_instance = task_instance

    @property
    def account(self) -> "Account":
        """获取任务关联的账号"""
        return self.task_instance.account

    def _create_task(self) -> Task:
        """创建任务实例"""
        return self._build_task(self.task_instance, self.account)

    def _update_status(self, status: TaskStatus, error: Optional[str] = None):
        """更新任务实例状态"""
        self._apply_task_status(
            task_instance=self.task_instance,
            account=self.account,
            status=status,
            error_message=error,
            clear_error_on_success=True,
        )

    def run(self):
        """
        执行任务的完整流程

        包含重试逻辑和错误处理。
        """
        # 设置日志上下文（端口号、账号昵称、任务名）
        from ptcgp_auto_v2.utils.logger import set_context, clear_context
        port = self.device.address.split(":")[-1] if ":" in self.device.address else self.device.address
        set_context(
            port=port,
            nickname=self.account.nickname or self.account.display_name,
            task=self.task_instance.task_type,
        )

        try:
            # 初始化组件
            self._init_components()

            # 检查是否收到停止信号
            if self._should_stop():
                logger.info("收到停止信号，取消执行")
                return

            # 更新状态为运行中
            self._update_status(TaskStatus.RUNNING)

            # 账号切换（如需要）
            if not self._is_current_account(self.account):
                if not self._switch_account(self.account):
                    self._update_status(TaskStatus.FAILED, "账号切换失败")
                    return

            # 重试循环
            last_error = None
            for attempt in range(self.config.max_retries):
                # 每次重试前检查停止信号
                if self._should_stop():
                    logger.info("收到停止信号，中断重试")
                    break

                try:
                    # 创建并执行任务
                    task = self._create_task()
                    result = task.execute()

                    if result.success:
                        if result.skipped:
                            # 跳过的任务设为 skipped 状态，不会被重复调度
                            logger.info(
                                f"任务跳过: {self.task_instance.task_type} ({result.skip_reason})"
                            )
                            self._apply_task_status(
                                task_instance=self.task_instance,
                                account=self.account,
                                status=TaskStatus.SKIPPED,
                                error_message=f"跳过: {result.skip_reason}",
                                clear_error_on_success=False,
                            )
                        else:
                            logger.info(
                                f"任务完成: {self.task_instance.task_type}"
                            )
                            self._update_status(TaskStatus.COMPLETED)
                        return
                    else:
                        last_error = result.error
                        logger.warning(
                            f"任务失败 (尝试 {attempt + 1}/{self.config.max_retries}): "
                            f"{result.error}"
                        )

                except RuntimeError as e:
                    last_error = str(e)
                    logger.exception(
                        f"任务异常 (尝试 {attempt + 1}/{self.config.max_retries}): {e}"
                    )

                # 如果不是最后一次尝试，进行恢复（但先检查停止信号）
                if attempt < self.config.max_retries - 1:
                    if self._should_stop():
                        logger.info("收到停止信号，跳过恢复")
                        break
                    self._try_recover()
                    time.sleep(self.config.retry_delay)

            # 超过最大重试次数
            logger.error(
                f"任务最终失败: {self.task_instance.task_type}"
            )
            self._update_status(TaskStatus.FAILED, last_error)

        except Exception as e:
            logger.exception(f"执行器异常: {e}")
            self._update_status(TaskStatus.FAILED, str(e))

        finally:
            self._cleanup()
            clear_context()


def run_executor(
    device: Device,
    task_instance: "TaskInstance",
    device_pool: DevicePool,
    config: Optional[ExecutorConfig] = None,
):
    """
    运行执行器的便捷函数

    可用于线程池提交。

    Args:
        device: 执行任务的设备
        task_instance: 任务实例
        device_pool: 设备池
        config: 执行器配置
    """
    executor = TaskExecutor(device, task_instance, device_pool, config)
    executor.run()


class AccountBatchExecutor(BaseExecutor):
    """
    账号批量任务执行器

    在一个设备上顺序执行账号的所有任务，避免频繁切换账号。
    任务按 task_plan 中定义的顺序执行。
    """

    def __init__(
        self,
        device: Device,
        account: "Account",
        task_instances: list["TaskInstance"],
        device_pool: DevicePool,
        config: Optional[ExecutorConfig] = None,
    ):
        """
        初始化批量执行器

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

    def _execute_single_task(self, task_instance: "TaskInstance"):
        """
        执行单个任务

        Args:
            task_instance: 任务实例
        """
        from ptcgp_auto_v2.utils.logger import set_context

        # 设置当前任务到日志上下文
        set_context(task=task_instance.task_type)

        logger.info(f"执行任务: {task_instance.task_type}")

        try:
            # 创建并执行任务
            task = self._build_task(task_instance, self.account)
            result = task.execute()

            # 更新任务状态
            if result.success:
                if result.skipped:
                    logger.info(
                        f"任务跳过: {task_instance.task_type} ({result.skip_reason})"
                    )
                    self._apply_task_status(
                        task_instance=task_instance,
                        account=self.account,
                        status=TaskStatus.SKIPPED,
                        error_message=f"跳过: {result.skip_reason}",
                        clear_error_on_success=False,
                    )
                else:
                    logger.info(f"任务完成: {task_instance.task_type}")
                    self._apply_task_status(
                        task_instance=task_instance,
                        account=self.account,
                        status=TaskStatus.COMPLETED,
                        clear_error_on_success=True,
                    )
            else:
                logger.error(f"任务失败: {task_instance.task_type} - {result.error}")
                self._apply_task_status(
                    task_instance=task_instance,
                    account=self.account,
                    status=TaskStatus.FAILED,
                    error_message=result.error,
                    clear_error_on_success=False,
                )

        except RuntimeError as e:
            logger.exception(f"任务执行异常: {task_instance.task_type} - {e}")
            self._apply_task_status(
                task_instance=task_instance,
                account=self.account,
                status=TaskStatus.FAILED,
                error_message=str(e),
                clear_error_on_success=False,
            )

    def run(self):
        """
        执行账号的所有批量任务

        按顺序执行所有任务，单个任务失败不影响后续任务执行。
        """
        from ptcgp_auto_v2.utils.logger import set_context, clear_context

        port = (
            self.device.address.split(":")[-1]
            if ":" in self.device.address
            else self.device.address
        )
        set_context(
            port=port, nickname=self.account.nickname or self.account.display_name
        )

        task_types = [t.task_type for t in self.task_instances]
        logger.info(f"开始批量执行 {len(self.task_instances)} 个任务: {task_types}")

        try:
            # 初始化组件
            self._init_components()

            # 检查是否收到停止信号
            if self._should_stop():
                logger.info("收到停止信号，取消执行")
                return

            # 账号切换（如需要）
            if not self._is_current_account(self.account):
                if not self._switch_account(self.account):
                    # 账号切换失败，将所有任务标记为失败
                    for task_instance in self.task_instances:
                        task_instance.status = TaskStatus.FAILED.value
                        task_instance.error_message = "账号切换失败"
                        task_instance.updated_at = datetime.now()
                        task_instance.save()
                    logger.error("账号切换失败，终止批量任务")
                    return

            # 顺序执行所有任务
            for task_instance in self.task_instances:
                # 检查停止信号
                if self._should_stop():
                    logger.info("收到停止信号，中断任务执行")
                    # 剩余任务保持 running 状态，重启后会被重置为 pending
                    break

                # 执行单个任务（失败继续执行后续任务）
                self._execute_single_task(task_instance)

            logger.info(f"批量任务执行完成 (账号: {self.account.nickname})")

        except RuntimeError as e:
            logger.exception(f"批量执行器异常: {e}")
            # 将所有仍为 running 状态的任务标记为失败
            for task_instance in self.task_instances:
                if task_instance.status == TaskStatus.RUNNING.value:
                    self._apply_task_status(
                        task_instance=task_instance,
                        account=self.account,
                        status=TaskStatus.FAILED,
                        error_message=str(e),
                        clear_error_on_success=False,
                    )

        finally:
            self._cleanup()
            clear_context()


def run_account_batch_executor(
    device: Device,
    account: "Account",
    task_instances: list["TaskInstance"],
    device_pool: DevicePool,
    config: Optional[ExecutorConfig] = None,
):
    """
    运行账号批量执行器的便捷函数

    可用于线程池提交。

    Args:
        device: 执行任务的设备
        account: 账号
        task_instances: 按顺序排列的任务实例列表
        device_pool: 设备池
        config: 执行器配置
    """
    executor = AccountBatchExecutor(device, account, task_instances, device_pool, config)
    executor.run()
