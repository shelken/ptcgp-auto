# -*- coding: utf-8 -*-
"""
调度器模块

中心调度器，负责管理设备池、生成任务实例、分配任务到空闲设备。
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil
from typing import Any, Optional

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.executor import (
    AccountExecutor,
    ExecutorConfig,
    TaskInstanceSnapshot,
)
from ptcgp_auto_v2.core.task_base import TaskRegistry
from ptcgp_auto_v2.core.scheduling_service import (
    build_account_scheduling_context,
    get_effective_reset_type,
    resolve_account_dispatch_plan,
    should_reset_task,
)
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.infra.account_syncer import AccountSnapshot
from ptcgp_auto_v2.utils.bluestacks_manager import (
    extract_port_from_address,
    list_manageable_instances,
    start_bluestacks_instance,
    stop_bluestacks_instance,
)
from ptcgp_auto_v2.utils.device_discovery import discover_devices

from ptcgp_auto_v2.core.account_creation import check_and_trigger_account_creation

logger = logging.getLogger(__name__)


DEFAULT_POLL_INTERVAL = 5.0  # 轮询间隔（秒）
DEFAULT_MAX_WORKERS = 4  # 最大并发执行器数
DEFAULT_TASK_GENERATION_INTERVAL = 60.0  # 任务生成检查间隔（秒）
DEFAULT_STALE_TASK_TIMEOUT = 600.0  # running/blocked 任务超时时间（秒），默认 10 分钟
DEFAULT_SKIPPED_RESET_TIMEOUT = 3600.0  # skipped 任务重置时间（秒），默认 1 小时
DEFAULT_STALE_CHECK_INTERVAL = 60.0  # 异常任务检查间隔（秒）


@dataclass
class SchedulerConfig:
    """调度器配置"""

    poll_interval: float = DEFAULT_POLL_INTERVAL
    max_workers: int = DEFAULT_MAX_WORKERS
    task_generation_interval: float = DEFAULT_TASK_GENERATION_INTERVAL
    stale_task_timeout: float = DEFAULT_STALE_TASK_TIMEOUT
    skipped_reset_timeout: float = DEFAULT_SKIPPED_RESET_TIMEOUT
    stale_task_check_interval: float = DEFAULT_STALE_CHECK_INTERVAL
    init_first: bool = False  # 是否优先执行 init_account 任务
    executor_config: ExecutorConfig = field(default_factory=ExecutorConfig)


class Scheduler:
    """
    中心调度器

    职责：
    1. 管理设备池
    2. 生成待执行任务（每日/每周重置）
    3. 分配任务到空闲设备
    4. 监控执行状态
    """

    def __init__(
        self,
        device_addresses: list[str],
        config: Optional[SchedulerConfig] = None,
    ):
        """
        初始化调度器

        Args:
            device_addresses: ADB 设备地址列表
            config: 调度器配置
        """
        self._settings = get_settings()
        self.config = config or SchedulerConfig()

        self.device_pool = DevicePool(device_addresses)
        self._running = False
        self._stop_event = threading.Event()  # 停止事件，用于通知执行器
        self._executor_pool: Optional[ThreadPoolExecutor] = None
        self._last_task_generation = datetime.min
        self._last_stale_check = datetime.min  # 上次异常任务检查时间
        self._last_auto_scale_check = datetime.min  # 上次扩缩容检查时间
        self._lock = threading.Lock()
        self._active_account_ids: set[int] = set()  # 进程内活跃账号防重

    @property
    def settings(self):
        """全局配置"""
        return self._settings

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行"""
        return self._running

    @contextmanager
    def _repository_scope(self):
        """为一次高层调度动作提供统一的 Repository 工厂。"""
        with session_scope() as session:
            yield RepositoryFactory(session)

    def _should_generate_tasks(self) -> bool:
        """检查是否应该生成任务"""
        elapsed = (datetime.now() - self._last_task_generation).total_seconds()
        return elapsed >= self.config.task_generation_interval

    def _should_check_stale_tasks(self) -> bool:
        """检查是否应该检查异常任务"""
        elapsed = (datetime.now() - self._last_stale_check).total_seconds()
        return elapsed >= self.config.stale_task_check_interval

    def _should_auto_scale(self) -> bool:
        """检查是否应该执行扩缩容评估"""
        elapsed = (datetime.now() - self._last_auto_scale_check).total_seconds()
        return elapsed >= self._settings.auto_scale_eval_interval_seconds

    def _check_and_reset_stale_tasks(self):
        """检查并重置超时的异常任务"""
        if not self._should_check_stale_tasks():
            return

        self._last_stale_check = datetime.now()
        active_account_ids = self._snapshot_active_account_ids()
        with self._repository_scope() as repos:
            reset_count = repos.task_instances().reset_stale_tasks(
                stale_timeout_seconds=int(self.config.stale_task_timeout),
                skipped_timeout_seconds=int(self.config.skipped_reset_timeout),
                exclude_account_ids=active_account_ids,
                force_all=False,
            )
        if reset_count > 0:
            logger.info(f"已重置 {reset_count} 个超时/异常状态的任务为待执行")

    def _snapshot_active_account_ids(self) -> list[int]:
        """获取当前活跃账号快照（线程安全）。"""
        with self._lock:
            return list(self._active_account_ids)

    def _is_account_active(self, account_id: int) -> bool:
        """检查账号是否已被当前调度器占用。"""
        with self._lock:
            return account_id in self._active_account_ids

    def _mark_account_active(self, account_id: Optional[int]):
        """标记账号为活跃状态，防止重复派发。"""
        if account_id is None:
            return
        with self._lock:
            self._active_account_ids.add(account_id)

    def _unmark_account_active(self, account_id: Optional[int]):
        """解除账号活跃标记。"""
        if account_id is None:
            return
        with self._lock:
            self._active_account_ids.discard(account_id)

    def _bind_account_release_on_future(self, future, account_id: Optional[int]):
        """为 Future 绑定账号释放回调。"""
        if account_id is None:
            return

        def _done_callback(done_future):
            try:
                exc = None
                if hasattr(done_future, "exception"):
                    exc = done_future.exception()
                if exc:
                    logger.exception(
                        "账号任务执行异常 (account_id=%s): %s", account_id, exc
                    )
            except Exception:
                logger.exception(
                    "读取账号任务 Future 结果失败 (account_id=%s)", account_id
                )
            finally:
                self._unmark_account_active(account_id)

        future.add_done_callback(_done_callback)

    def _count_pending_tasks(self) -> int:
        """统计 pending 任务数量"""
        with self._repository_scope() as repos:
            pending_count = repos.task_instances().count_by_status(
                TaskStatus.PENDING.value
            )
        logger.info("当前 pending 任务数量: %s", pending_count)
        return pending_count

    def _calculate_target_device_count(self, pending_count: int) -> int:
        """根据 pending 数量计算目标设备数。"""
        if pending_count <= 0:
            return min(
                self._settings.auto_scale_max_devices,
                max(0, self._settings.auto_scale_min_idle_devices),
            )
        return min(
            self._settings.auto_scale_max_devices,
            ceil(pending_count / self._settings.auto_scale_pending_step),
        )

    def _pick_stoppable_idle_devices(
        self,
        count: int,
        manageable_ports: set[int],
    ) -> list[Device]:
        """选择允许缩容的空闲 auto 设备。"""
        if count <= 0:
            return []

        now = datetime.now()
        candidates: list[Device] = []
        for device in self.device_pool.get_idle_devices():
            port = extract_port_from_address(device.address)
            if port is None or port not in manageable_ports:
                continue

            idle_at = device.became_idle_at
            if idle_at is None:
                continue
            if (now - idle_at).total_seconds() < self._settings.auto_scale_idle_seconds:
                continue

            candidates.append(device)

        candidates.sort(key=lambda device: device.became_idle_at or datetime.min)
        return candidates[:count]

    def _refresh_device_pool(self, addresses: Optional[list[str]] = None):
        """刷新设备池（发现新增/移除的设备）"""
        if addresses is None:
            addresses = discover_devices()
        current_addresses = {d.address for d in self.device_pool.get_all_devices()}
        new_addresses = set(addresses) - current_addresses
        removed_addresses = current_addresses - set(addresses)

        for address in new_addresses:
            self.device_pool.add_device(address)

        for address in removed_addresses:
            self.device_pool.remove_device(address)

    def _auto_scale_evaluate(self):
        """执行自动扩缩容评估"""
        if not self._settings.auto_scale_emulators:
            return
        if not self._should_auto_scale():
            return

        self._last_auto_scale_check = datetime.now()

        pending_count = self._count_pending_tasks()
        running_devices = discover_devices()
        # 先用当前真实运行设备刷新池，避免使用过期设备快照导致 idle 统计虚高
        self._refresh_device_pool(running_devices)
        idle_count = self.device_pool.available_count
        running_count = len(running_devices)

        pending_step = self._settings.auto_scale_pending_step
        if pending_step <= 0:
            logger.warning(
                "自动扩缩容 pending_step 配置非法: %s",
                pending_step,
            )
            return

        target_devices = self._calculate_target_device_count(pending_count)
        manageable_map = list_manageable_instances(
            prefix=self._settings.auto_scale_instance_prefix,
        )
        manageable_ports = set(manageable_map.keys())
        running_ports = {
            port
            for address in running_devices
            if (port := extract_port_from_address(address)) is not None
        }
        running_auto_ports = running_ports & manageable_ports

        logger.debug(
            "扩缩容评估: pending=%s idle=%s running=%s target=%s manageable=%s",
            pending_count,
            idle_count,
            running_count,
            target_devices,
            len(manageable_map),
        )

        to_start = max(0, target_devices - running_count)
        if to_start > 0:
            candidates = [
                instance_name
                for port, (instance_name, _) in manageable_map.items()
                if port not in running_auto_ports
            ]
            if not candidates:
                logger.warning("没有可启动的 auto 实例，请检查 conf 配置")
            for instance_name in candidates[:to_start]:
                start_bluestacks_instance(instance_name)

        to_stop = max(0, running_count - target_devices)
        if to_stop > 0:
            idle_devices = self._pick_stoppable_idle_devices(
                to_stop,
                manageable_ports,
            )
            for device in idle_devices:
                port = extract_port_from_address(device.address)
                if port is None:
                    continue
                auto_info = manageable_map.get(port)
                if auto_info is None:
                    continue
                instance, auto_name = auto_info
                logger.info(
                    "准备关闭 BlueStacks 实例: %s (auto: %s, 设备: %s)",
                    instance,
                    auto_name,
                    device.address,
                )
                if stop_bluestacks_instance(instance):
                    self.device_pool.remove_device(device.address)

        # 缩容后再次以实时状态刷新，防止已关闭设备被旧快照重新加入设备池
        self._refresh_device_pool(discover_devices())

    def _generate_pending_tasks(self):
        """
        生成待执行任务

        检查每个账号的任务计划，根据重置规则生成新的任务实例。
        支持多 Plan 聚合和自定义频率。
        """
        if not self._should_generate_tasks():
            return

        logger.debug("检查并生成待执行任务...")
        self._last_task_generation = datetime.now()

        try:
            with self._repository_scope() as repos:
                accounts = repos.accounts().get_all()
                task_instance_repo = repos.task_instances()
                for account in accounts:
                    scheduling_context = build_account_scheduling_context(account)
                    if not scheduling_context.aggregated_config:
                        continue

                    for task_type, config in scheduling_context.aggregated_config.items():
                        self._ensure_task_instance(
                            account,
                            task_type,
                            config,
                            task_instance_repo,
                        )

        except RuntimeError as e:
            logger.exception(f"生成任务失败: {e}")

    def _ensure_task_instance(
        self,
        account,
        task_type: str,
        config: dict[str, Any] | None = None,
        task_instance_repo=None,
    ) -> None:
        """
        确保账号的任务实例存在且状态正确

        Args:
            account: 账号
            task_type: 任务类型
            config: 任务配置（覆盖默认配置）
        """
        if config is None:
            config = {}

        # 获取任务类以确定默认重置类型
        task_class = TaskRegistry.get_or_none(task_type)
        if not task_class:
            logger.warning(f"未知的任务类型: {task_type}")
            return

        # 确定重置类型：配置覆盖 > 默认
        reset_type = get_effective_reset_type(task_class, config)

        # 查找或创建任务实例
        if task_instance_repo is None:
            raise RuntimeError("task_instance_repo 未提供")

        instance = task_instance_repo.get_or_create(
            account_id=account.id,
            task_type=task_type,
            reset_type=reset_type,
        )

        # 检查是否需要重置
        if should_reset_task(instance, reset_type, config):
            logger.info(
                f"重置任务: {task_type} (账号: {account.nickname}, 规则: {reset_type})"
            )
            if instance.id is None:
                raise RuntimeError("任务实例 ID 为空，无法重置")
            instance.status = TaskStatus.PENDING.value
            instance.next_run_at = None
            instance.reset_type = reset_type
            task_instance_repo.update_runtime_state(
                instance.id,
                status=TaskStatus.PENDING.value,
                next_run_at=None,
                reset_type=reset_type,
            )

    def _get_next_account_batch(
        self,
    ) -> Optional[tuple[AccountSnapshot, list[TaskInstanceSnapshot]]]:
        """
        获取下一个有待执行任务的账号及其所有待执行任务

        按账号级别批量调度，避免频繁切换账号。
        优先返回有待执行 init_account 任务的账号，确保新账号优先初始化。

        Returns:
            (Account, task_instances_list) 或 None
        """
        with self._repository_scope() as repos:
            task_instance_repo = repos.task_instances()
            account_repo = repos.accounts()
            account_ids = task_instance_repo.get_accounts_with_pending_tasks()
            if not account_ids:
                return None

            pending_tasks_map = task_instance_repo.get_pending_by_account_ids(
                account_ids
            )
            running_account_ids = task_instance_repo.get_running_account_ids(
                account_ids
            )
            accounts_map = account_repo.get_by_ids(account_ids)

            for account_id in account_ids:
                if self._is_account_active(account_id):
                    continue
                if account_id in running_account_ids:
                    continue

                account = accounts_map.get(account_id)
                if account is None:
                    continue

                pending_tasks = pending_tasks_map.get(account_id, [])
                if not pending_tasks:
                    continue

                scheduling_context = build_account_scheduling_context(account)
                dispatch_plan = resolve_account_dispatch_plan(
                    account,
                    pending_tasks,
                    scheduling_context,
                )
                ordered_tasks = list(dispatch_plan.ordered_tasks)
                prerequisite_task_type = dispatch_plan.missing_prerequisite_task_type
                if prerequisite_task_type is not None:
                    prerequisite_task = self._get_or_reset_prerequisite_instance(
                        account_id=account_id,
                        task_type=prerequisite_task_type,
                        task_instance_repo=task_instance_repo,
                    )
                    ordered_tasks = [prerequisite_task, *ordered_tasks]

                account_snapshot = AccountSnapshot.from_account(account)
                task_snapshots = [
                    TaskInstanceSnapshot.from_instance(task) for task in ordered_tasks
                ]
                return (account_snapshot, task_snapshots)

        return None

    def _dispatch_account_tasks(
        self, account: AccountSnapshot, task_instances: list[TaskInstanceSnapshot]
    ):
        """
        批量分配账号的所有任务到同一设备执行

        Args:
            account: 账号
            task_instances: 按顺序排列的任务列表
        """
        # 获取设备（优先获取已登录该账号的设备）
        if account.id is None:
            raise RuntimeError("账号快照缺少 ID，无法分配设备")
        device = self.device_pool.acquire_for_account(account.id)
        if not device:
            logger.debug(f"账号 {account.display_name} 没有可用设备，等待...")
            return

        self._submit_account_executor(device, account, task_instances)

    def _get_or_reset_prerequisite_instance(
        self,
        account_id: int,
        task_type: str,
        task_instance_repo,
    ):
        """获取前置任务实例并保证其为 pending 状态。"""
        task_class = TaskRegistry.get(task_type)
        return task_instance_repo.ensure_pending(
            account_id=account_id,
            task_type=task_type,
            reset_type=task_class.reset_type.value,
        )

    def _trigger_multi_device_creation(self):
        """
        触发多设备并发创建新账号（后台异步执行，不阻塞主循环）

        让所有空闲设备同时开始创建新账号，直到没有空闲设备或达到账号上限。
        使用线程池并发启动，主循环立即返回继续调度其他任务。
        """
        available = self.device_pool.available_count
        if available == 0:
            return

        # 计算还可以创建多少账号
        with self._repository_scope() as repos:
            current_count = repos.accounts().count_all()
        remaining = self._settings.max_accounts - current_count
        if remaining <= 0:
            logger.debug(
                f"账号数量 ({current_count}) 已达上限 ({self._settings.max_accounts})"
            )
            return

        # 创建数量 = min(空闲设备数, 剩余可创建数)
        create_count = min(available, remaining)
        logger.info(f"触发多设备创建: {create_count} 个设备将在后台开始创建新账号")

        # 【修复】使用调度器线程池后台执行，不阻塞主循环
        # 每个任务提交后立即返回，异常由回调函数处理
        def _creation_done_callback(future):
            """账号创建任务完成后的回调"""
            try:
                result = future.result()
                if result:
                    logger.debug("后台账号创建任务成功完成")
                else:
                    logger.debug("后台账号创建任务未成功（可能设备已被占用或达到上限）")
            except Exception as e:
                logger.exception(f"后台账号创建任务异常: {e}")

        executor_pool = self._executor_pool
        if executor_pool is None:
            raise RuntimeError("调度器线程池未初始化")

        for _ in range(create_count):
            future = executor_pool.submit(check_and_trigger_account_creation, self)
            future.add_done_callback(_creation_done_callback)

    def _build_executor_config(self) -> ExecutorConfig:
        """构建带停止事件的执行器配置"""
        return ExecutorConfig(
            max_retries=self.config.executor_config.max_retries,
            retry_delay=self.config.executor_config.retry_delay,
            recovery_delay=self.config.executor_config.recovery_delay,
            app_package=self.config.executor_config.app_package,
            template_threshold=self.config.executor_config.template_threshold,
            auto_scale_instance_prefix=self._settings.auto_scale_instance_prefix,
            stop_event=self._stop_event,
        )

    def _submit_account_executor(
        self,
        device: Device,
        account: AccountSnapshot,
        task_instances: list[TaskInstanceSnapshot],
    ):
        """提交账号任务执行。"""
        if account.id is None:
            raise RuntimeError("账号快照缺少 ID，无法提交执行器")
        self._mark_account_active(account.id)

        # 将所有任务状态改为 running，防止被其他线程分配
        with self._repository_scope() as repos:
            task_instance_repo = repos.task_instances()
            task_instance_repo.set_status_for_ids(
                [
                    task_instance.id
                    for task_instance in task_instances
                    if task_instance.id is not None
                ],
                TaskStatus.RUNNING.value,
            )
            for task_instance in task_instances:
                task_instance.status = TaskStatus.RUNNING.value

        task_types = [t.task_type for t in task_instances]
        logger.debug(
            f"分配批量任务: {task_types} "
            f"(账号: {account.display_name}, 设备: {device.address})"
        )

        executor_config = self._build_executor_config()
        executor_pool = self._executor_pool
        if executor_pool is None:
            raise RuntimeError("调度器线程池未初始化")
        try:
            executor = AccountExecutor(
                device=device,
                account=account,
                task_instances=task_instances,
                device_pool=self.device_pool,
                config=executor_config,
            )
            future = executor_pool.submit(executor.run)
        except Exception:
            self._unmark_account_active(account.id)
            raise
        self._bind_account_release_on_future(future, account.id)

    def _main_loop(self):
        """调度器主循环（批量任务调度）"""
        while self._running:
            try:
                # 生成待执行任务
                self._generate_pending_tasks()

                # 检查并重置超时的异常任务
                self._check_and_reset_stale_tasks()

                # 自动扩缩容评估
                self._auto_scale_evaluate()

                # 检查是否有空闲设备
                if self.device_pool.available_count == 0:
                    time.sleep(self.config.poll_interval)
                    continue

                batch = self._get_next_account_batch()

                # init_first: 账号未满时持续优先创建账号；若已有 init_account 任务则先执行 init_account
                if self.config.init_first and self._settings.auto_create_accounts:
                    with self._repository_scope() as repos:
                        account_count = repos.accounts().count_all()
                    if account_count < self._settings.max_accounts:
                        if batch:
                            account, task_instances = batch
                            has_init_task = any(
                                task.task_type == "init_account"
                                for task in task_instances
                            )
                            if has_init_task:
                                self._dispatch_account_tasks(account, task_instances)
                                continue

                        self._trigger_multi_device_creation()
                        time.sleep(self.config.poll_interval)
                        continue

                if batch:
                    # 有待执行任务，优先执行
                    account, task_instances = batch
                    self._dispatch_account_tasks(account, task_instances)
                elif self._settings.auto_create_accounts:
                    # 没有待执行任务，且启用自动创建，为每个空闲设备创建新账号
                    self._trigger_multi_device_creation()
                    time.sleep(self.config.poll_interval)

            except RuntimeError as e:
                logger.exception(f"调度器主循环异常: {e}")
                time.sleep(self.config.poll_interval)

    def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        logger.info("启动调度器...")
        self._running = True
        self._executor_pool = ThreadPoolExecutor(
            max_workers=self.config.max_workers,
            thread_name_prefix="TaskExecutor",
        )

        # 在新线程中运行主循环
        self._main_thread = threading.Thread(
            target=self._main_loop,
            name="SchedulerMainLoop",
            daemon=True,
        )
        self._main_thread.start()
        logger.info(
            f"调度器已启动 (设备数: {self.device_pool.total_count}, "
            f"最大并发: {self.config.max_workers})"
        )

    def stop(self, wait: bool = True):
        """
        停止调度器

        Args:
            wait: 是否等待所有任务完成
        """
        if not self._running:
            return

        logger.info("停止调度器...")
        self._running = False
        self._stop_event.set()  # 通知所有执行器停止

        if self._executor_pool:
            self._executor_pool.shutdown(wait=wait)
            self._executor_pool = None

        if hasattr(self, "_main_thread") and self._main_thread.is_alive():
            self._main_thread.join(timeout=10)

        logger.info("调度器已停止")

    def run(self):
        """
        运行调度器（阻塞模式）

        在当前线程运行，直到收到停止信号。
        """
        logger.info("启动调度器（阻塞模式）...")
        self._running = True
        self._executor_pool = ThreadPoolExecutor(
            max_workers=self.config.max_workers,
            thread_name_prefix="TaskExecutor",
        )

        try:
            logger.info(
                f"调度器已启动 (设备数: {self.device_pool.total_count}, "
                f"最大并发: {self.config.max_workers})"
            )
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        finally:
            self.stop(wait=True)

    def get_status(self) -> dict[str, Any]:
        """
        获取调度器状态

        Returns:
            包含调度器状态信息的字典
        """
        device_status = self.device_pool.get_status_summary()

        with self._repository_scope() as repos:
            task_instance_repo = repos.task_instances()
            pending_count = task_instance_repo.count_by_status(TaskStatus.PENDING.value)
            running_count = task_instance_repo.count_by_status(TaskStatus.RUNNING.value)

        return {
            "running": self._running,
            "devices": device_status,
            "tasks": {
                "pending": pending_count,
                "running": running_count,
            },
        }

    def run_single_task(
        self,
        device_address: str,
        account_id: int,
        task_type: str,
    ) -> bool:
        """
        运行单个任务（用于调试）

        如果账号信息不完整，会自动先执行前置任务（如 fetch_account_info），
        然后再执行用户指定的任务。

        Args:
            device_address: 设备地址
            account_id: 账号 ID
            task_type: 任务类型

        Returns:
            True 表示任务成功
        """
        from ptcgp_auto_v2.core.executor import AccountExecutor

        logger.info(f"运行单个任务: {task_type} (账号 ID: {account_id})")

        with self._repository_scope() as repos:
            account = repos.accounts().get_by_id(account_id)
            if not account:
                logger.error(f"账号不存在: {account_id}")
                return False

            task_class = TaskRegistry.get(task_type)
            task_instance_repo = repos.task_instances()
            instance = task_instance_repo.get_or_create(
                account_id=account_id,
                task_type=task_type,
                reset_type=task_class.reset_type.value,
            )

            dispatch_plan = resolve_account_dispatch_plan(account, [instance])
            tasks = list(dispatch_plan.ordered_tasks)
            prerequisite_task_type = dispatch_plan.missing_prerequisite_task_type
            if prerequisite_task_type is not None:
                prerequisite_task = self._get_or_reset_prerequisite_instance(
                    account_id=account_id,
                    task_type=prerequisite_task_type,
                    task_instance_repo=task_instance_repo,
                )
                tasks = [prerequisite_task, *tasks]
            task_ids = [task.id for task in tasks if task.id is not None]
            if len(task_ids) != len(tasks):
                raise RuntimeError("任务实例缺少 ID，无法执行")
            task_instance_repo.set_status_for_ids(
                task_ids,
                TaskStatus.RUNNING.value,
            )
            for task in tasks:
                task.status = TaskStatus.RUNNING.value
            account_snapshot = AccountSnapshot.from_account(account)
            task_snapshots = [
                TaskInstanceSnapshot.from_instance(task) for task in tasks
            ]
            instance_id = instance.id

        if instance_id is None:
            raise RuntimeError(
                f"任务实例不存在: task_type={task_type}, account_id={account_id}"
            )

        # 创建临时设备池
        temp_pool = DevicePool([device_address])
        device = temp_pool.acquire()
        if not device:
            logger.error("无法获取设备")
            return False

        # 使用 AccountExecutor 执行（统一逻辑）
        executor = AccountExecutor(
            device=device,
            account=account_snapshot,
            task_instances=task_snapshots,
            device_pool=temp_pool,
            config=self.config.executor_config,
        )
        executor.run()

        # 刷新任务实例状态
        with self._repository_scope() as repos:
            instance = repos.task_instances().get_by_id(instance_id)
            final_status = instance.status if instance is not None else None
        if final_status is None:
            raise RuntimeError(
                f"任务实例不存在: task_type={task_type}, account_id={account_id}"
            )
        return final_status in {
            TaskStatus.COMPLETED.value,
            TaskStatus.SKIPPED.value,
        }
