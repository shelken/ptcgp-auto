# -*- coding: utf-8 -*-
"""
调度器模块

中心调度器，负责管理设备池、生成任务实例、分配任务到空闲设备。
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, TYPE_CHECKING

from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.executor import (
    ExecutorConfig,
    run_executor,
    run_account_batch_executor,
)
from ptcgp_auto_v2.core.task_base import TaskRegistry, TaskStatus, ResetType

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import TaskInstance, Account
    from ptcgp_auto_v2.db.repositories import TaskInstanceRepository, AccountRepository

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
    executor_config: ExecutorConfig = field(default_factory=ExecutorConfig)
    # 自动创建账号配置
    auto_create_accounts: bool = False  # 是否启用自动创建账号
    max_accounts: int = 100  # 最大账号数量上限


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
        auto_create_accounts: bool = False,
        max_accounts: int = 100,
    ):
        """
        初始化调度器

        Args:
            device_addresses: ADB 设备地址列表
            config: 调度器配置
            auto_create_accounts: 是否启用自动创建账号
            max_accounts: 最大账号数量上限
        """
        self.config = config or SchedulerConfig()
        # 如果传入了自动创建参数，覆盖配置中的默认值
        if auto_create_accounts:
            self.config.auto_create_accounts = auto_create_accounts
        if max_accounts != 100:  # 只有当不是默认值时才覆盖
            self.config.max_accounts = max_accounts

        self.device_pool = DevicePool(device_addresses)
        self._running = False
        self._stop_event = threading.Event()  # 停止事件，用于通知执行器
        self._executor_pool: Optional[ThreadPoolExecutor] = None
        self._last_task_generation = datetime.min
        self._last_stale_check = datetime.min  # 上次异常任务检查时间
        self._lock = threading.Lock()

        # 延迟初始化的仓库
        self._task_instance_repo: Optional["TaskInstanceRepository"] = None
        self._account_repo: Optional["AccountRepository"] = None

    def _init_repositories(self):
        """初始化数据仓库"""
        from ptcgp_auto_v2.db.repositories import (
            TaskInstanceRepository,
            AccountRepository,
        )

        self._task_instance_repo = TaskInstanceRepository()
        self._account_repo = AccountRepository()

        # 启动时自动重置异常状态的任务
        reset_count = self._task_instance_repo.reset_all_pending()
        if reset_count > 0:
            logger.info(f"已重置 {reset_count} 个异常状态的任务为待执行")

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行"""
        return self._running

    def _should_generate_tasks(self) -> bool:
        """检查是否应该生成任务"""
        elapsed = (datetime.now() - self._last_task_generation).total_seconds()
        return elapsed >= self.config.task_generation_interval

    def _should_check_stale_tasks(self) -> bool:
        """检查是否应该检查异常任务"""
        elapsed = (datetime.now() - self._last_stale_check).total_seconds()
        return elapsed >= self.config.stale_task_check_interval

    def _has_creating_account(self) -> bool:
        """检查是否已有账号正在创建中（存在 pending init_account 任务）"""
        if not self._task_instance_repo:
            return False

        # 查找所有 init_account 类型的任务实例
        from ptcgp_auto_v2.db.models import TaskInstance
        from sqlmodel import select
        from ptcgp_auto_v2.db.engine import get_engine
        from sqlmodel import Session

        with Session(get_engine()) as session:
            statement = select(TaskInstance).where(
                TaskInstance.task_type == "init_account",
                TaskInstance.status.in_(["pending", "running"]),
            )
            result = session.exec(statement).first()
            return result is not None

    def _check_and_reset_stale_tasks(self):
        """检查并重置超时的异常任务"""
        if not self._should_check_stale_tasks():
            return

        self._last_stale_check = datetime.now()
        reset_count = self._task_instance_repo.reset_stale_tasks(
            stale_timeout_seconds=int(self.config.stale_task_timeout),
            skipped_timeout_seconds=int(self.config.skipped_reset_timeout),
        )
        if reset_count > 0:
            logger.info(f"已重置 {reset_count} 个超时/异常状态的任务为待执行")

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
            # 获取所有有任务计划的账号（旧关联或新关联）
            # 注意：get_accounts_with_plans 可能只查了旧关联，需要确保能查到所有
            # 暂时遍历所有账号可能更安全，或者依赖 Repository 的优化
            accounts = self._account_repo.get_all()

            for account in accounts:
                task_configs = self._aggregate_account_plans(account)
                if not task_configs:
                    continue

                for task_type, config in task_configs.items():
                    self._ensure_task_instance(account, task_type, config)

        except RuntimeError as e:
            logger.exception(f"生成任务失败: {e}")

    def _aggregate_account_plans(self, account) -> dict[str, dict]:
        """
        聚合账号的所有任务计划配置

        Returns:
            Dict[task_type, config_dict] - 按优先级最高的 Plan 的任务顺序排列
        """
        aggregated = {}

        if not account.task_plan_associations:
            return aggregated

        # 处理多 Plan
        # 按优先级降序排序 (priority 越高越先处理，保证高优先级 Plan 的任务顺序优先)
        associations = sorted(account.task_plan_associations, key=lambda x: -x.priority)

        # 第一步：收集所有任务类型（按优先级从高到低）
        all_task_types_ordered = []
        for assoc in associations:
            if not assoc.is_active:
                continue
            plan = assoc.task_plan
            if not plan:
                continue
            # 高优先级 Plan 的任务排在前面
            for task_type in plan.task_types_list:
                if task_type not in all_task_types_ordered:
                    all_task_types_ordered.append(task_type)

        # 第二步：收集所有配置（低优先级先处理，但只更新配置不改变顺序）
        # 反转顺序，让低优先级先处理
        associations_low_to_high = list(reversed(associations))
        for assoc in associations_low_to_high:
            if not assoc.is_active:
                continue
            plan = assoc.task_plan
            if not plan:
                continue

            for task_type in plan.task_types_list:
                plan_config = plan.config_dict.get(task_type, {})
                if task_type in aggregated:
                    # 如果已存在，合并字典（新 Plan 覆盖旧的）
                    aggregated[task_type].update(plan_config)
                else:
                    aggregated[task_type] = plan_config.copy()

        # 第三步：按优先级最高的 Plan 的任务顺序重新排列字典
        # 使用 Python 3.7+ 的字典有序特性
        ordered_aggregated = {}
        for task_type in all_task_types_ordered:
            if task_type in aggregated:
                ordered_aggregated[task_type] = aggregated[task_type]

        return ordered_aggregated

    def _ensure_task_instance(
        self,
        account: "Account",
        task_type: str,
        config: dict[str, Any] | None = None,
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
        reset_type_str = config.get("reset_type")
        if reset_type_str:
            try:
                reset_type = ResetType(reset_type_str)
            except ValueError:
                logger.warning(f"无效的 reset_type: {reset_type_str}，使用默认值")
                reset_type = task_class.reset_type
        else:
            reset_type = task_class.reset_type

        # 查找或创建任务实例
        instance = self._task_instance_repo.get_or_create(
            account_id=account.id,
            task_type=task_type,
            reset_type=reset_type.value,
        )

        # 检查是否需要重置
        if self._should_reset_task(instance, reset_type, config):
            logger.info(
                f"重置任务: {task_type} (账号: {account.nickname}, 规则: {reset_type.value})"
            )
            instance.status = TaskStatus.PENDING.value
            # 如果 reset_type 变了，更新数据库
            if instance.reset_type != reset_type.value:
                instance.reset_type = reset_type.value
            instance.save()

    def _should_reset_task(
        self,
        instance: "TaskInstance",
        reset_type: ResetType,
        config: dict[str, Any] | None = None,
    ) -> bool:
        """
        检查任务是否应该重置

        Args:
            instance: 任务实例
            reset_type: 重置类型
            config: 任务配置（可选，包含 interval_seconds 等）

        Returns:
            True 表示应该重置
        """
        if config is None:
            config = {}
        # 如果任务未完成，不需要重置
        if instance.status != TaskStatus.COMPLETED.value:
            return False

        # 如果没有完成时间，不需要重置
        if not instance.last_completed_at:
            return False

        now = datetime.now()
        last_completed = instance.last_completed_at

        if reset_type == ResetType.DAILY:
            # 检查是否跨天
            return last_completed.date() < now.date()

        elif reset_type == ResetType.WEEKLY:
            # 检查是否跨周（假设周一重置）
            last_week = last_completed.isocalendar()[1]
            current_week = now.isocalendar()[1]
            return last_week != current_week or last_completed.year != now.year

        elif reset_type == ResetType.ONCE:
            # 一次性任务不重置
            return False

        elif reset_type == ResetType.INTERVAL:
            # 按时间间隔重置
            interval = config.get("interval_seconds", 3600)  # 默认 1 小时
            return (now - last_completed).total_seconds() >= interval

        return False

    def _get_next_task(self) -> Optional["TaskInstance"]:
        """
        获取下一个待执行任务

        优先级：
        1. 状态为 pending
        2. 该账号没有正在执行的任务（防止同一账号被分配到多个设备）
        3. 创建时间早的优先

        Returns:
            TaskInstance 或 None
        """
        return self._task_instance_repo.get_next_pending_excluding_busy_accounts()

    def _get_next_account_batch(
        self,
    ) -> Optional[tuple["Account", list["TaskInstance"]]]:
        """
        获取下一个有待执行任务的账号及其所有待执行任务

        按账号级别批量调度，避免频繁切换账号。
        优先返回有待执行 init_account 任务的账号，确保新账号优先初始化。

        Returns:
            (Account, task_instances_list) 或 None
        """
        # 获取所有有待执行任务的账号
        account_ids = self._task_instance_repo.get_accounts_with_pending_tasks()

        # 分离有 init_account 任务的账号和其他账号
        init_account_ids = []
        other_account_ids = []
        for account_id in account_ids:
            pending_tasks = self._task_instance_repo.get_pending_by_account(account_id)
            has_init = any(
                task.task_type == "init_account"
                and task.status == TaskStatus.PENDING.value
                for task in pending_tasks
            )
            if has_init:
                init_account_ids.append(account_id)
            else:
                other_account_ids.append(account_id)

        # 优先处理有 init_account 的账号
        ordered_account_ids = init_account_ids + other_account_ids

        for account_id in ordered_account_ids:
            # 检查该账号是否已经有正在执行的任务
            if self._task_instance_repo.has_running_tasks(account_id):
                continue

            # 获取账号信息
            account = self._account_repo.get_by_id(account_id)
            if not account:
                continue

            # 获取该账号的所有待执行任务
            pending_tasks = self._task_instance_repo.get_pending_by_account(account_id)
            if not pending_tasks:
                continue

            # 检查未完成的新号初始化任务（断点恢复支持）
            init_task = self._get_incomplete_init_task(pending_tasks)
            if init_task:
                # 仅执行 init_account 任务，跳过其他任务
                pending_tasks = [init_task]

            # 检查是否需要前置任务（如 fetch_account_info）
            pending_tasks = self._ensure_prerequisites_in_batch(account, pending_tasks)

            # 按照任务计划顺序排列
            ordered_tasks = self._order_tasks_by_plan(account, pending_tasks)

            return (account, ordered_tasks)

        return None

    def _ensure_prerequisites_in_batch(
        self, account: "Account", tasks: list["TaskInstance"]
    ) -> list["TaskInstance"]:
        """
        确保批量任务包含必要的前置任务

        如果账号信息不完整，在任务列表开头插入 fetch_account_info 任务。

        Args:
            account: 账号
            tasks: 待执行任务列表

        Returns:
            可能添加了前置任务的任务列表
        """
        return self._ensure_fetch_account_info(account, tasks)

    def _order_tasks_by_plan(
        self, account: "Account", tasks: list["TaskInstance"]
    ) -> list["TaskInstance"]:
        """
        按照账号的主任务计划顺序排列任务

        主计划定义为优先级最高且启用的计划。

        Args:
            account: 账号
            tasks: 待排序的任务列表

        Returns:
            按主计划 task_types 顺序排列的任务列表
        """
        if not account.task_plan_associations:
            # 没有任务计划，按创建时间排序
            return sorted(tasks, key=lambda x: x.created_at or datetime.min)

        # 找到所有激活的计划
        active_assocs = [a for a in account.task_plan_associations if a.is_active]
        if not active_assocs:
            return sorted(tasks, key=lambda x: x.created_at or datetime.min)

        # 排序：优先级降序，ID 升序 (保证稳定性)
        active_assocs.sort(key=lambda x: (-x.priority, x.task_plan_id))

        # 【修复】合并所有 Plan 的 task_types 顺序（按优先级从高到低）
        # 确保即使任务不在 primary_plan 中，也能按照包含它的 Plan 的顺序排列
        merged_task_order = []
        for assoc in active_assocs:
            plan = assoc.task_plan
            if not plan or not plan.task_types_list:
                continue
            for task_type in plan.task_types_list:
                if task_type not in merged_task_order:
                    merged_task_order.append(task_type)

        if not merged_task_order:
            return sorted(tasks, key=lambda x: x.created_at or datetime.min)

        # 按照合并后的 task_types 顺序排列
        plan_order = {task_type: idx for idx, task_type in enumerate(merged_task_order)}
        # 不在任何计划中的任务排在最后，再按创建时间排序
        return sorted(
            tasks,
            key=lambda x: (
                plan_order.get(x.task_type, 999),
                x.created_at or datetime.min,
            ),
        )

    def _dispatch_account_batch(
        self, account: "Account", task_instances: list["TaskInstance"]
    ):
        """
        批量分配账号的所有任务到同一设备执行

        Args:
            account: 账号
            task_instances: 按顺序排列的任务列表
        """
        # 获取设备（优先获取已登录该账号的设备）
        device = self.device_pool.acquire_for_account(account.id)
        if not device:
            logger.debug(f"账号 {account.nickname} 没有可用设备，等待...")
            return

        self._submit_account_batch_executor(device, account, task_instances)

    def _ensure_fetch_account_info(
        self, account: "Account", tasks: list["TaskInstance"]
    ) -> list["TaskInstance"]:
        """确保任务列表包含 fetch_account_info 前置任务"""
        from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask

        if not FetchAccountInfoTask.needs_fetch(account, tasks):
            return tasks

        has_fetch_task = any(t.task_type == "fetch_account_info" for t in tasks)
        if has_fetch_task:
            return tasks

        prereq_instance = self._get_or_reset_prerequisite_instance(
            account_id=account.id,
            task_type="fetch_account_info",
        )

        tasks.insert(0, prereq_instance)
        logger.debug(
            f"批量任务插入前置任务: fetch_account_info (账号: {account.nickname})"
        )

        return tasks

    def _get_or_reset_prerequisite_instance(self, account_id: int, task_type: str):
        """获取前置任务实例并保证其为 pending 状态"""
        task_class = TaskRegistry.get(task_type)
        prerequisite = self._task_instance_repo.get_or_create(
            account_id=account_id,
            task_type=task_type,
            reset_type=task_class.reset_type.value,
        )

        if prerequisite.status != TaskStatus.PENDING.value:
            prerequisite.status = TaskStatus.PENDING.value
            prerequisite.save()

        return prerequisite

    def _insert_prerequisite_task(
        self, original_task: "TaskInstance", prerequisite_type: str
    ):
        """
        在原任务前插入前置任务

        将原任务状态改为 blocked，创建前置任务优先执行。

        Args:
            original_task: 原任务实例
            prerequisite_type: 前置任务类型
        """
        # 将原任务改为 blocked，等待前置任务完成后重新调度
        original_task.status = TaskStatus.BLOCKED.value
        original_task.save()

        prerequisite = self._get_or_reset_prerequisite_instance(
            account_id=original_task.account_id,
            task_type=prerequisite_type,
        )

        logger.info(
            f"插入前置任务: {prerequisite_type} -> {original_task.task_type} "
            f"(账号: {original_task.account.nickname})"
        )

    def _get_incomplete_init_task(
        self, tasks: list["TaskInstance"]
    ) -> "TaskInstance | None":
        """
        查找未完成的新号初始化任务

        检查任务列表中是否存在状态非 completed/skipped 的 init_account 任务。
        用于断点恢复：确保新号在初始化完成前只执行 init_account 任务。

        Args:
            tasks: 待检查的任务列表

        Returns:
            未完成的 init_account 任务，若不存在则返回 None
        """
        for task in tasks:
            if task.task_type == "init_account" and task.status not in (
                TaskStatus.COMPLETED.value,
                TaskStatus.SKIPPED.value,
            ):
                return task
        return None

    def _get_next_non_init_batch(
        self,
    ) -> Optional[tuple["Account", list["TaskInstance"]]]:
        """
        获取下一个有待执行非init_account任务的账号

        优先处理现有账号的其他任务（如open_pack, claim_rewards等），
        让新账号创建在系统空闲时进行。

        Returns:
            (Account, task_instances_list) 或 None
        """
        # 获取所有有待执行任务的账号
        account_ids = self._task_instance_repo.get_accounts_with_pending_tasks()

        for account_id in account_ids:
            # 检查该账号是否已经有正在执行的任务
            if self._task_instance_repo.has_running_tasks(account_id):
                continue

            # 获取账号信息
            account = self._account_repo.get_by_id(account_id)
            if not account:
                continue

            # 获取该账号的所有待执行任务
            pending_tasks = self._task_instance_repo.get_pending_by_account(account_id)
            if not pending_tasks:
                continue

            # 【关键】过滤掉 init_account 任务，只处理其他任务
            non_init_tasks = [t for t in pending_tasks if t.task_type != "init_account"]

            if not non_init_tasks:
                # 只有 init_account 任务，跳过这个账号
                continue

            # 检查是否需要前置任务（如 fetch_account_info）
            non_init_tasks = self._ensure_prerequisites_in_batch(
                account, non_init_tasks
            )

            # 按照任务计划顺序排列
            ordered_tasks = self._order_tasks_by_plan(account, non_init_tasks)

            return (account, ordered_tasks)

        return None

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
        current_count = self._account_repo.count_all()
        remaining = self.config.max_accounts - current_count
        if remaining <= 0:
            logger.debug(
                f"账号数量 ({current_count}) 已达上限 ({self.config.max_accounts})"
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

        for _ in range(create_count):
            future = self._executor_pool.submit(
                check_and_trigger_account_creation, self
            )
            future.add_done_callback(_creation_done_callback)

    def _build_executor_config(self) -> ExecutorConfig:
        """构建带停止事件的执行器配置"""
        return ExecutorConfig(
            max_retries=self.config.executor_config.max_retries,
            retry_delay=self.config.executor_config.retry_delay,
            recovery_delay=self.config.executor_config.recovery_delay,
            app_package=self.config.executor_config.app_package,
            stop_event=self._stop_event,
        )

    def _submit_task_executor(self, device: Device, task_instance: "TaskInstance"):
        """提交单任务执行"""
        # 【关键】在提交到线程池之前，立即将状态改为 running
        # 防止同一账号的任务被分配到多个设备
        task_instance.status = TaskStatus.RUNNING.value
        task_instance.save()

        logger.debug(
            f"分配任务: {task_instance.task_type} "
            f"(账号: {task_instance.account.nickname}, "
            f"设备: {device.address})"
        )

        executor_config = self._build_executor_config()
        self._executor_pool.submit(
            run_executor,
            device=device,
            task_instance=task_instance,
            device_pool=self.device_pool,
            config=executor_config,
        )

    def _submit_account_batch_executor(
        self,
        device: Device,
        account: "Account",
        task_instances: list["TaskInstance"],
    ):
        """提交批量任务执行"""
        # 将所有任务状态改为 running，防止被其他线程分配
        for task_instance in task_instances:
            task_instance.status = TaskStatus.RUNNING.value
            task_instance.save()

        task_types = [t.task_type for t in task_instances]
        logger.debug(
            f"分配批量任务: {task_types} "
            f"(账号: {account.nickname}, 设备: {device.address})"
        )

        executor_config = self._build_executor_config()
        self._executor_pool.submit(
            run_account_batch_executor,
            device=device,
            account=account,
            task_instances=task_instances,
            device_pool=self.device_pool,
            config=executor_config,
        )

    def _main_loop(self):
        """调度器主循环（批量任务调度）"""
        while self._running:
            try:
                # 生成待执行任务
                self._generate_pending_tasks()

                # 检查并重置超时的异常任务
                self._check_and_reset_stale_tasks()

                # 检查是否有空闲设备
                if self.device_pool.available_count == 0:
                    time.sleep(self.config.poll_interval)
                    continue

                # 【修复】优先执行所有待处理任务（包括init_account）
                # 只有在完全没有待执行任务时才创建新账号
                batch = self._get_next_account_batch()
                if batch:
                    # 有待执行任务，优先执行
                    account, task_instances = batch
                    self._dispatch_account_batch(account, task_instances)
                elif self.config.auto_create_accounts:
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
        self._init_repositories()
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
        self._init_repositories()
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

        pending_count = 0
        running_count = 0
        if self._task_instance_repo:
            pending_count = self._task_instance_repo.count_by_status(
                TaskStatus.PENDING.value
            )
            running_count = self._task_instance_repo.count_by_status(
                TaskStatus.RUNNING.value
            )

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
        from ptcgp_auto_v2.core.executor import AccountBatchExecutor

        logger.info(f"运行单个任务: {task_type} (账号 ID: {account_id})")

        self._init_repositories()

        # 获取账号
        account = self._account_repo.get_by_id(account_id)
        if not account:
            logger.error(f"账号不存在: {account_id}")
            return False

        # 获取或创建任务实例
        task_class = TaskRegistry.get(task_type)
        instance = self._task_instance_repo.get_or_create(
            account_id=account_id,
            task_type=task_type,
            reset_type=task_class.reset_type.value,
        )

        # 构建任务列表（自动添加前置任务）
        tasks = self._ensure_prerequisites_in_batch(account, [instance])

        # 创建临时设备池
        temp_pool = DevicePool([device_address])
        device = temp_pool.acquire()
        if not device:
            logger.error("无法获取设备")
            return False

        # 使用 AccountBatchExecutor 执行（统一逻辑）
        executor = AccountBatchExecutor(
            device=device,
            account=account,
            task_instances=tasks,
            device_pool=temp_pool,
            config=self.config.executor_config,
        )
        executor.run()

        # 刷新任务实例状态
        instance = self._task_instance_repo.get_by_id(instance.id)
        return instance.status in {
            TaskStatus.COMPLETED.value,
            TaskStatus.SKIPPED.value,
        }
