# -*- coding: utf-8 -*-
"""
主调度器自动创建账号功能

集成到主调度器中，在主循环中检查条件并触发新账号创建。
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.scheduler import Scheduler

logger = logging.getLogger(__name__)

# 账号创建冷却时间（秒）
ACCOUNT_CREATION_COOLDOWN = 60.0

# 上次触发创建的时间戳（全局变量，跨调用保持）
_last_creation_time: float = 0.0


def check_and_trigger_account_creation(scheduler: "Scheduler") -> bool:
    """
    检查并触发新账号创建

    当满足以下条件时，重置一个空闲设备的环境，让游戏自动进入新账号创建流程：
    1. 启用了自动创建账号 (auto_create_accounts=True)
    2. 当前账号数 < 最大账号数
    3. 存在空闲设备
    4. 没有正在创建中的账号（没有 pending init_account 任务）

    Args:
        scheduler: 调度器实例

    Returns:
        True 如果触发了创建，False 否则
    """
    global _last_creation_time

    # 1. 检查是否启用自动创建
    if not scheduler.config.auto_create_accounts:
        return False

    # 2. 检查冷却时间（避免频繁重置）
    import time

    current_time = time.time()
    elapsed = current_time - _last_creation_time
    if elapsed < ACCOUNT_CREATION_COOLDOWN:
        logger.debug(
            f"距离上次创建触发仅 {elapsed:.1f} 秒，冷却中 ({ACCOUNT_CREATION_COOLDOWN} 秒)"
        )
        return False

    # 2. 检查账号数是否达上限
    if not scheduler._account_repo:
        return False

    current_count = scheduler._account_repo.count_all()
    if current_count >= scheduler.config.max_accounts:
        logger.debug(
            f"账号数量 ({current_count}) 已达上限 ({scheduler.config.max_accounts})，跳过创建"
        )
        return False

    # 3. 检查是否有空闲设备
    if scheduler.device_pool.available_count == 0:
        logger.debug("没有空闲设备，跳过创建")
        return False

    # 4. 检查是否已有正在创建中的账号
    if scheduler._has_creating_account():
        logger.debug("已有账号正在创建中，跳过创建")
        return False

    # 5. 获取空闲设备并重置环境
    device = scheduler.device_pool.acquire()
    if not device:
        return False

    try:
        logger.info(f"准备创建新账号，重置设备 {device.address} 环境")

        # 初始化 ADB 并重置环境
        from ptcgp_auto_v2.infra.adb import AdbController
        from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher

        adb = AdbController(device.address)
        if not adb.connect():
            logger.warning(f"无法连接设备 {device.address}")
            return False

        try:
            switcher = AccountSwitcher(adb)
            switcher.reset_game_environment()

            # 重启游戏，进入新账号创建流程
            from ptcgp_auto_v2.config.settings import get_settings

            settings = get_settings()
            adb.restart_app(settings.app_package)
            logger.info(f"设备 {device.address} 已重置并重启游戏，等待新账号创建")
            return True

        finally:
            adb.disconnect()

    except Exception as e:
        logger.exception(f"触发新账号创建失败: {e}")
        return False
    finally:
        # 归还设备，让主调度器正常分配任务
        scheduler.device_pool.release(device)
