# -*- coding: utf-8 -*-
"""
任务执行器模块

负责在指定设备上执行任务，包括账号切换、任务执行和状态更新。
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ptcgp_auto_v2.core.device_pool import Device, DevicePool
from ptcgp_auto_v2.core.task_base import Task, TaskRegistry, TaskResult, TaskStatus
from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.locales.zh_Hant import TEXT_PATTERNS
from ptcgp_auto_v2.utils.common_handlers import build_common_handlers

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account, TaskInstance

logger = logging.getLogger(__name__)


@dataclass
class ExecutorConfig:
    """执行器配置"""

    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 30.0  # 重试间隔（秒）
    recovery_delay: float = 5.0  # 恢复等待时间（秒）
    app_package: str = "jp.pokemon.pokemontcgp"
    stop_event: Optional[threading.Event] = field(default=None)  # 停止事件


class TaskExecutor:
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
        self.device = device
        self.task_instance = task_instance
        self.device_pool = device_pool
        self.config = config or ExecutorConfig()

        # 延迟初始化的组件（在 run 时创建）
        self._adb = None
        self._recognizer = None
        self._page_detector = None
        self._account_switcher = None
        self._account_syncer = None

    @property
    def account(self) -> "Account":
        """获取任务关联的账号"""
        return self.task_instance.account

    def _should_stop(self) -> bool:
        """检查是否应该停止执行"""
        if self.config.stop_event and self.config.stop_event.is_set():
            return True
        return False

    def _init_components(self):
        """初始化基础设施组件"""
        # 延迟导入，避免循环依赖
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
        template_matcher = TemplateMatcher()
        self._recognizer = (ocr_engine, template_matcher)
        self._page_detector = PageDetector(
            adb=self._adb,
            ocr_engine=ocr_engine,
            template_matcher=template_matcher,
        )
        self._page_detector.load_base_pages(COMMON_PAGES)
        self._account_switcher = AccountSwitcher(self._adb)
        self._account_syncer = AccountSyncer(self._adb)

    def _is_current_account(self) -> bool:
        """
        检查设备当前是否已登录目标账号

        通过从设备提取账号 XML 并比较来确定当前登录的账号。
        同时会比较设备与数据库的 session_token_iat，如果设备更新则同步到数据库。
        """
        # 始终从设备获取当前账号（同时会比较 iat 并同步）
        current_account = self._account_syncer.get_current_account()
        if current_account:
            # 更新设备缓存
            self.device.update_current_account(current_account.id)
            logger.debug(
                f"设备当前账号: {current_account.nickname or current_account.game_id}"
            )
            return current_account.id == self.account.id

        # 无法获取当前账号（可能设备未 Root 或无账号登录）
        logger.warning("无法获取设备当前账号，将尝试切换")
        return False

    def _switch_account(self) -> bool:
        """
        切换到目标账号

        Returns:
            True 表示切换成功
        """
        logger.info(f"切换账号: {self.account.nickname} (ID: {self.account.id})")
        try:
            # 使用账号切换器注入 XML
            success = self._account_switcher.switch_to(self.account)
            if success:
                self.device.update_current_account(self.account.id)
                # 重启应用以应用账号切换
                self._restart_app()
            return success
        except Exception as e:
            logger.error(f"账号切换失败: {e}")
            return False

    def _restart_app(self):
        """重启游戏应用"""
        logger.debug("重启游戏应用...")
        self._adb.force_stop(self.config.app_package)
        time.sleep(2)
        self._adb.start_app(self.config.app_package)
        time.sleep(self.config.recovery_delay)

    def _try_recover(self):
        """尝试恢复到可执行状态"""
        logger.info("尝试恢复执行状态...")
        self._restart_app()

    def _create_task(self) -> Task:
        """创建任务实例"""
        task_class = TaskRegistry.get(self.task_instance.task_type)

        # 加载任务专用页面规则
        self._page_detector.load_task_pages(task_class.pages)

        # 创建任务实例
        task = task_class(
            adb=self._adb,
            recognizer=self._recognizer,
            page_detector=self._page_detector,
        )
        task.register_handlers(
            build_common_handlers(self._adb, self._page_detector, TEXT_PATTERNS)
        )
        task.bind_account(self.account)

        # 传递停止事件给任务
        if self.config.stop_event:
            task.set_stop_event(self.config.stop_event)

        return task

    def _update_status(self, status: TaskStatus, error: Optional[str] = None):
        """更新任务实例状态"""
        self.task_instance.status = status.value
        if status == TaskStatus.COMPLETED:
            self.task_instance.last_completed_at = datetime.now()
            # 恢复被阻塞的任务（前置任务完成后）
            self._unblock_dependent_tasks()
        if error:
            self.task_instance.error_message = error
        self.task_instance.updated_at = datetime.now()
        # 保存到数据库
        self.task_instance.save()

    def _unblock_dependent_tasks(self):
        """恢复该账号被阻塞的任务"""
        from ptcgp_auto_v2.db.repositories import TaskInstanceRepository

        repo = TaskInstanceRepository()
        blocked_tasks = repo.get_blocked_by_account(self.account.id)
        for task in blocked_tasks:
            logger.info(
                f"恢复被阻塞任务: {task.task_type} (账号: {self.account.nickname})"
            )
            task.status = TaskStatus.PENDING.value
            task.save()

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
            if not self._is_current_account():
                if not self._switch_account():
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
                            self.task_instance.status = TaskStatus.SKIPPED.value
                            self.task_instance.error_message = f"跳过: {result.skip_reason}"
                            self.task_instance.save()
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

                except Exception as e:
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
            # 停止前同步最后的账号 XML（更新 iat）
            if self._account_syncer:
                try:
                    self._account_syncer.get_current_account()
                    logger.debug("已同步设备账号 XML")
                except Exception as e:
                    logger.warning(f"同步账号 XML 失败: {e}")

            if self._adb:
                self._adb.disconnect()
            # 归还设备
            self.device_pool.release(self.device)
            logger.debug(f"设备已归还: {self.device.address}")
            # 清除日志上下文
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


class AccountBatchExecutor:
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
        self.device = device
        self.account = account
        self.task_instances = task_instances
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
        template_matcher = TemplateMatcher()
        self._recognizer = (ocr_engine, template_matcher)
        self._page_detector = PageDetector(
            adb=self._adb,
            ocr_engine=ocr_engine,
            template_matcher=template_matcher,
        )
        self._page_detector.load_base_pages(COMMON_PAGES)
        self._account_switcher = AccountSwitcher(self._adb)
        self._account_syncer = AccountSyncer(self._adb)

    def _is_current_account(self) -> bool:
        """检查设备当前是否已登录目标账号"""
        current_account = self._account_syncer.get_current_account()
        if current_account:
            self.device.update_current_account(current_account.id)
            logger.debug(
                f"设备当前账号: {current_account.nickname or current_account.game_id}"
            )
            return current_account.id == self.account.id

        logger.warning("无法获取设备当前账号，将尝试切换")
        return False

    def _switch_account(self) -> bool:
        """切换到目标账号"""
        logger.info(f"切换账号: {self.account.nickname} (ID: {self.account.id})")
        try:
            success = self._account_switcher.switch_to(self.account)
            if success:
                self.device.update_current_account(self.account.id)
                self._restart_app()
            return success
        except Exception as e:
            logger.error(f"账号切换失败: {e}")
            return False

    def _restart_app(self):
        """重启游戏应用"""
        logger.debug("重启游戏应用...")
        self._adb.force_stop(self.config.app_package)
        time.sleep(2)
        self._adb.start_app(self.config.app_package)
        time.sleep(self.config.recovery_delay)

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
            # 获取任务类
            task_class = TaskRegistry.get(task_instance.task_type)

            # 加载任务专用页面规则
            self._page_detector.load_task_pages(task_class.pages)

            # 创建任务实例
            task = task_class(
                adb=self._adb,
                recognizer=self._recognizer,
                page_detector=self._page_detector,
            )
            task.register_handlers(
                build_common_handlers(self._adb, self._page_detector, TEXT_PATTERNS)
            )
            task.bind_account(self.account)

            # 传递停止事件给任务
            if self.config.stop_event:
                task.set_stop_event(self.config.stop_event)

            # 执行任务
            result = task.execute()

            # 更新任务状态
            if result.success:
                if result.skipped:
                    logger.info(
                        f"任务跳过: {task_instance.task_type} ({result.skip_reason})"
                    )
                    task_instance.status = TaskStatus.SKIPPED.value
                    task_instance.error_message = f"跳过: {result.skip_reason}"
                else:
                    logger.info(f"任务完成: {task_instance.task_type}")
                    task_instance.status = TaskStatus.COMPLETED.value
                    task_instance.last_completed_at = datetime.now()
                    task_instance.error_message = None
                    # 恢复被阻塞的任务
                    self._unblock_dependent_tasks()
            else:
                logger.error(f"任务失败: {task_instance.task_type} - {result.error}")
                task_instance.status = TaskStatus.FAILED.value
                task_instance.error_message = result.error

            task_instance.updated_at = datetime.now()
            task_instance.save()

        except Exception as e:
            logger.exception(f"任务执行异常: {task_instance.task_type} - {e}")
            task_instance.status = TaskStatus.FAILED.value
            task_instance.error_message = str(e)
            task_instance.updated_at = datetime.now()
            task_instance.save()

    def _unblock_dependent_tasks(self):
        """恢复该账号被阻塞的任务"""
        from ptcgp_auto_v2.db.repositories import TaskInstanceRepository

        repo = TaskInstanceRepository()
        blocked_tasks = repo.get_blocked_by_account(self.account.id)
        for task in blocked_tasks:
            logger.info(
                f"恢复被阻塞任务: {task.task_type} (账号: {self.account.nickname})"
            )
            task.status = TaskStatus.PENDING.value
            task.save()

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
            if not self._is_current_account():
                if not self._switch_account():
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

        except Exception as e:
            logger.exception(f"批量执行器异常: {e}")
            # 将所有仍为 running 状态的任务标记为失败
            for task_instance in self.task_instances:
                if task_instance.status == TaskStatus.RUNNING.value:
                    task_instance.status = TaskStatus.FAILED.value
                    task_instance.error_message = str(e)
                    task_instance.updated_at = datetime.now()
                    task_instance.save()

        finally:
            # 同步账号 XML
            if self._account_syncer:
                try:
                    self._account_syncer.get_current_account()
                    logger.debug("已同步设备账号 XML")
                except Exception as e:
                    logger.warning(f"同步账号 XML 失败: {e}")

            if self._adb:
                self._adb.disconnect()
            # 归还设备
            self.device_pool.release(self.device)
            logger.debug(f"设备已归还: {self.device.address}")
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
