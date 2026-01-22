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
from typing import Callable, Optional, TYPE_CHECKING

from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.executor import (
    TaskExecutor,
    ExecutorConfig,
    run_executor,
    run_account_batch_executor,
)
from ptcgp_auto_v2.core.task_base import TaskRegistry, TaskStatus, ResetType

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import TaskInstance, Account
    from ptcgp_auto_v2.db.repositories import TaskInstanceRepository, AccountRepository

logger = logging.getLogger(__name__)


@dataclass
class SchedulerConfig:
    """调度器配置"""
    poll_interval: float = 5.0           # 轮询间隔（秒）
    max_workers: int = 4                  # 最大并发执行器数
    task_generation_interval: float = 60.0  # 任务生成检查间隔（秒）
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
        self.config = config or SchedulerConfig()
        self.device_pool = DevicePool(device_addresses)
        self._running = False
        self._stop_event = threading.Event()  # 停止事件，用于通知执行器
        self._executor_pool: Optional[ThreadPoolExecutor] = None
        self._last_task_generation = datetime.min
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

    def _generate_pending_tasks(self):
        """
        生成待执行任务

        检查每个账号的任务计划，根据重置规则生成新的任务实例。
        """
        if not self._should_generate_tasks():
            return

        logger.debug("检查并生成待执行任务...")
        self._last_task_generation = datetime.now()

        try:
            # 获取所有有任务计划的账号
            accounts = self._account_repo.get_accounts_with_plans()

            for account in accounts:
                if not account.task_plan:
                    continue

                for task_type in account.task_plan.task_types:
                    self._ensure_task_instance(account, task_type)

        except Exception as e:
            logger.exception(f"生成任务失败: {e}")

    def _ensure_task_instance(self, account, task_type: str):
        """
        确保账号的任务实例存在且状态正确

        Args:
            account: 账号
            task_type: 任务类型
        """
        # 获取任务类以确定重置类型
        task_class = TaskRegistry.get_or_none(task_type)
        if not task_class:
            logger.warning(f"未知的任务类型: {task_type}")
            return

        reset_type = task_class.reset_type

        # 查找或创建任务实例
        instance = self._task_instance_repo.get_or_create(
            account_id=account.id,
            task_type=task_type,
            reset_type=reset_type.value,
        )

        # 检查是否需要重置
        if self._should_reset_task(instance, reset_type):
            logger.info(
                f"重置任务: {task_type} (账号: {account.nickname})"
            )
            instance.status = TaskStatus.PENDING.value
            instance.save()

    def _should_reset_task(self, instance: "TaskInstance", reset_type: ResetType) -> bool:
        """
        检查任务是否应该重置

        Args:
            instance: 任务实例
            reset_type: 重置类型

        Returns:
            True 表示应该重置
        """
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
        # 检查是否需要 fetch_account_info
        from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask

        if not FetchAccountInfoTask.needs_fetch(account):
            return tasks

        # 检查任务列表中是否已有 fetch_account_info
        has_fetch_task = any(t.task_type == "fetch_account_info" for t in tasks)
        if has_fetch_task:
            return tasks

        # 创建或获取 fetch_account_info 任务实例
        task_class = TaskRegistry.get("fetch_account_info")
        prereq_instance = self._task_instance_repo.get_or_create(
            account_id=account.id,
            task_type="fetch_account_info",
            reset_type=task_class.reset_type.value,
        )

        # 确保前置任务是 pending 状态
        if prereq_instance.status != TaskStatus.PENDING.value:
            prereq_instance.status = TaskStatus.PENDING.value
            prereq_instance.save()

        # 插入到任务列表开头
        tasks.insert(0, prereq_instance)
        logger.info(f"批量任务插入前置任务: fetch_account_info (账号: {account.nickname})")

        return tasks

    def _order_tasks_by_plan(
        self, account: "Account", tasks: list["TaskInstance"]
    ) -> list["TaskInstance"]:
        """
        按照账号的 task_plan 顺序排列任务

        Args:
            account: 账号
            tasks: 待排序的任务列表

        Returns:
            按 task_plan.task_types 顺序排列的任务列表
        """
        if not account.task_plan or not account.task_plan.task_types:
            # 没有任务计划，按创建时间排序
            return sorted(tasks, key=lambda x: x.created_at or datetime.min)

        # 按照 task_plan.task_types 数组顺序排列
        plan_order = {
            task_type: idx
            for idx, task_type in enumerate(account.task_plan.task_types)
        }
        # 不在计划中的任务排在最后
        return sorted(tasks, key=lambda x: plan_order.get(x.task_type, 999))

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

        # 将所有任务状态改为 running，防止被其他线程分配
        for task_instance in task_instances:
            task_instance.status = TaskStatus.RUNNING.value
            task_instance.save()

        task_types = [t.task_type for t in task_instances]
        logger.info(
            f"分配批量任务: {task_types} "
            f"(账号: {account.nickname}, 设备: {device.address})"
        )

        # 创建带停止事件的执行器配置
        executor_config = ExecutorConfig(
            max_retries=self.config.executor_config.max_retries,
            retry_delay=self.config.executor_config.retry_delay,
            recovery_delay=self.config.executor_config.recovery_delay,
            app_package=self.config.executor_config.app_package,
            stop_event=self._stop_event,
        )

        # 提交到线程池执行批量任务
        self._executor_pool.submit(
            run_account_batch_executor,
            device=device,
            account=account,
            task_instances=task_instances,
            device_pool=self.device_pool,
            config=executor_config,
        )

    def _check_prerequisites(self, task_instance: "TaskInstance") -> Optional[str]:
        """
        检查任务是否有未满足的前置条件

        Args:
            task_instance: 待执行的任务实例

        Returns:
            需要执行的前置任务类型，或 None 表示无需前置任务
        """
        # 避免对 fetch_account_info 任务本身检查前置条件（防止循环）
        if task_instance.task_type == "fetch_account_info":
            return None

        # 使用 FetchAccountInfoTask 的判断方法检查账号信息完整性
        from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask
        if FetchAccountInfoTask.needs_fetch(task_instance.account):
            return "fetch_account_info"

        return None

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

        # 创建前置任务
        task_class = TaskRegistry.get(prerequisite_type)
        prerequisite = self._task_instance_repo.get_or_create(
            account_id=original_task.account_id,
            task_type=prerequisite_type,
            reset_type=task_class.reset_type.value,
        )

        # 确保前置任务是 pending 状态
        if prerequisite.status != TaskStatus.PENDING.value:
            prerequisite.status = TaskStatus.PENDING.value
            prerequisite.save()

        logger.info(
            f"插入前置任务: {prerequisite_type} -> {original_task.task_type} "
            f"(账号: {original_task.account.nickname})"
        )

    def _dispatch_task(self, task_instance: "TaskInstance"):
        """
        分配任务到设备执行

        Args:
            task_instance: 任务实例
        """
        # 检查是否需要前置任务
        prerequisite = self._check_prerequisites(task_instance)
        if prerequisite:
            # 插入前置任务并优先执行
            self._insert_prerequisite_task(task_instance, prerequisite)
            return

        # 获取设备（优先获取已登录该账号的设备）
        device = self.device_pool.acquire_for_account(task_instance.account_id)
        if not device:
            logger.debug("没有可用设备，等待...")
            return

        # 【关键】在提交到线程池之前，立即将状态改为 running
        # 防止同一账号的任务被分配到多个设备
        task_instance.status = TaskStatus.RUNNING.value
        task_instance.save()

        logger.info(
            f"分配任务: {task_instance.task_type} "
            f"(账号: {task_instance.account.nickname}, "
            f"设备: {device.address})"
        )

        # 创建带停止事件的执行器配置
        executor_config = ExecutorConfig(
            max_retries=self.config.executor_config.max_retries,
            retry_delay=self.config.executor_config.retry_delay,
            recovery_delay=self.config.executor_config.recovery_delay,
            app_package=self.config.executor_config.app_package,
            stop_event=self._stop_event,
        )

        # 提交到线程池执行
        self._executor_pool.submit(
            run_executor,
            device=device,
            task_instance=task_instance,
            device_pool=self.device_pool,
            config=executor_config,
        )

    def _main_loop(self):
        """调度器主循环（批量任务调度）"""
        while self._running:
            try:
                # 生成待执行任务
                self._generate_pending_tasks()

                # 检查是否有空闲设备
                if self.device_pool.available_count == 0:
                    time.sleep(self.config.poll_interval)
                    continue

                # 获取下一个账号的批量任务
                batch = self._get_next_account_batch()
                if not batch:
                    time.sleep(self.config.poll_interval)
                    continue

                account, task_instances = batch
                # 批量分配任务
                self._dispatch_account_batch(account, task_instances)

            except Exception as e:
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

    def get_status(self) -> dict:
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
        logger.info(f"运行单个任务: {task_type} (账号 ID: {account_id})")

        self._init_repositories()

        # 获取或创建任务实例
        task_class = TaskRegistry.get(task_type)
        instance = self._task_instance_repo.get_or_create(
            account_id=account_id,
            task_type=task_type,
            reset_type=task_class.reset_type.value,
        )

        # 检查是否需要前置任务
        prerequisite_type = self._check_prerequisites(instance)
        if prerequisite_type:
            logger.info(
                f"检测到需要前置任务: {prerequisite_type} -> {task_type} "
                f"(账号: {instance.account.nickname})"
            )
            # 先执行前置任务
            prereq_class = TaskRegistry.get(prerequisite_type)
            prereq_instance = self._task_instance_repo.get_or_create(
                account_id=account_id,
                task_type=prerequisite_type,
                reset_type=prereq_class.reset_type.value,
            )
            # 确保前置任务是 pending 状态
            if prereq_instance.status != TaskStatus.PENDING.value:
                prereq_instance.status = TaskStatus.PENDING.value
                prereq_instance.save()

            # 创建临时设备池并执行前置任务
            temp_pool = DevicePool([device_address])
            device = temp_pool.acquire()
            if not device:
                logger.error("无法获取设备")
                return False

            executor = TaskExecutor(
                device=device,
                task_instance=prereq_instance,
                device_pool=temp_pool,
                config=self.config.executor_config,
            )
            executor.run()

            # 检查前置任务是否成功
            if prereq_instance.status != TaskStatus.COMPLETED.value:
                logger.error(f"前置任务失败: {prerequisite_type}")
                return False

            # 刷新账号信息
            from ptcgp_auto_v2.db.repositories import AccountRepository
            updated_account = AccountRepository().get_by_id(account_id)
            if updated_account:
                instance.account = updated_account

            # 重新获取设备执行主任务
            device = temp_pool.acquire()
            if not device:
                logger.error("无法获取设备")
                return False
        else:
            # 无前置任务，直接创建设备池
            temp_pool = DevicePool([device_address])
            device = temp_pool.acquire()
            if not device:
                logger.error("无法获取设备")
                return False

        # 执行主任务
        executor = TaskExecutor(
            device=device,
            task_instance=instance,
            device_pool=temp_pool,
            config=self.config.executor_config,
        )
        executor.run()

        return instance.status == TaskStatus.COMPLETED.value
