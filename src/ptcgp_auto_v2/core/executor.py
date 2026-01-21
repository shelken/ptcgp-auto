# -*- coding: utf-8 -*-
"""
任务执行器模块

负责在指定设备上执行任务，包括账号切换、任务执行和状态更新。
"""

import logging
import time
from dataclasses import dataclass
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

        通过从设备提取账号 XML 并比较哈希来确定当前登录的账号。
        """
        # 首先检查内存缓存
        if self.device.current_account_id == self.account.id:
            return True

        # 如果缓存未命中，从设备实际获取当前账号
        current_account = self._account_syncer.get_current_account()
        if current_account:
            # 更新设备缓存
            self.device.current_account_id = current_account.id
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
                self.device.current_account_id = self.account.id
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

    def _box_center(self, box: tuple) -> tuple:
        """计算边界框中心点"""
        x1, y1, x2, y2 = box
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _ensure_account_info(self):
        """
        确保账号信息完整（friend_id、nickname、level）

        如果账号缺少必要信息，自动执行 FetchAccountInfoTask 获取。
        """
        from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask

        if not FetchAccountInfoTask.needs_fetch(self.account):
            return  # 信息完整，跳过

        logger.info(f"账号 {self.account.display_name} 信息不完整，自动获取...")

        # 加载任务页面规则
        self._page_detector.load_task_pages(FetchAccountInfoTask.pages)

        task = FetchAccountInfoTask(
            adb=self._adb,
            recognizer=self._recognizer,
            page_detector=self._page_detector,
        )
        task.bind_account(self.account)

        if task.setup():
            for _ in range(15):
                result = task.check_completion()
                if result:
                    break
                page_name, _ = self._page_detector.detect()
                ocr_results = self._page_detector.get_last_ocr_results()
                page_info = {
                    "name": page_name,
                    "ocr_results": [
                        (r["text"], self._box_center(r["box"])) for r in ocr_results
                    ],
                }
                action_result = task.process_page(page_info)
                time.sleep(action_result.should_wait)
            task.cleanup()

        # 清理任务页面规则
        self._page_detector.clear_task_pages()

        # 刷新账号信息到内存
        from ptcgp_auto_v2.db.repositories import AccountRepository

        updated = AccountRepository().get_by_id(self.account.id)
        if updated:
            self.task_instance.account = updated

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
        return task

    def _update_status(self, status: TaskStatus, error: Optional[str] = None):
        """更新任务实例状态"""
        self.task_instance.status = status.value
        if status == TaskStatus.COMPLETED:
            self.task_instance.last_completed_at = datetime.now()
        if error:
            self.task_instance.error_message = error
        self.task_instance.updated_at = datetime.now()
        # 保存到数据库
        self.task_instance.save()

    def run(self):
        """
        执行任务的完整流程

        包含重试逻辑和错误处理。
        """
        try:
            # 初始化组件
            self._init_components()

            # 更新状态为运行中
            self._update_status(TaskStatus.RUNNING)

            # 账号切换（如需要）
            if not self._is_current_account():
                if not self._switch_account():
                    self._update_status(TaskStatus.FAILED, "账号切换失败")
                    return

            # 确保账号信息完整（自动获取 friend_id）
            self._ensure_account_info()

            # 重试循环
            last_error = None
            for attempt in range(self.config.max_retries):
                try:
                    # 创建并执行任务
                    task = self._create_task()
                    result = task.execute()

                    if result.success:
                        logger.info(
                            f"任务完成: {self.task_instance.task_type} "
                            f"(账号: {self.account.nickname})"
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

                # 如果不是最后一次尝试，进行恢复
                if attempt < self.config.max_retries - 1:
                    self._try_recover()
                    time.sleep(self.config.retry_delay)

            # 超过最大重试次数
            logger.error(
                f"任务最终失败: {self.task_instance.task_type} "
                f"(账号: {self.account.nickname})"
            )
            self._update_status(TaskStatus.FAILED, last_error)

        except Exception as e:
            logger.exception(f"执行器异常: {e}")
            self._update_status(TaskStatus.FAILED, str(e))

        finally:
            if self._adb:
                self._adb.disconnect()
            # 归还设备
            self.device_pool.release(self.device)
            logger.debug(f"设备已归还: {self.device.address}")


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
