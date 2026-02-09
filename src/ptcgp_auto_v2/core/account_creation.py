# -*- coding: utf-8 -*-
"""
主调度器自动创建账号功能

集成到主调度器中，在主循环中检查条件并触发新账号创建。
"""

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ptcgp_auto_v2.core.scheduler import Scheduler

logger = logging.getLogger(__name__)

# 注：冷却时间已移除，允许多设备并发创建


def check_and_trigger_account_creation(scheduler: "Scheduler") -> bool:
    """
    检查并触发新账号创建

    当满足以下条件时，重置一个空闲设备的环境，让游戏自动进入新账号创建流程：
    1. 启用了自动创建账号 (auto_create_accounts=True)
    2. 当前账号数 < 最大账号数
    3. 存在空闲设备

    支持多设备并发创建。

    Args:
        scheduler: 调度器实例

    Returns:
        True 如果触发了创建，False 否则
    """
    # 1. 检查是否启用自动创建
    if not scheduler.settings.auto_create_accounts:
        return False

    # 2. 检查账号数是否达上限
    if not scheduler._account_repo:
        return False

    current_count = scheduler._account_repo.count_all()
    if current_count >= scheduler.settings.max_accounts:
        logger.debug(
            f"账号数量 ({current_count}) 已达上限 ({scheduler.settings.max_accounts})，跳过创建"
        )
        return False

    # 3. 检查是否有空闲设备
    if scheduler.device_pool.available_count == 0:
        logger.debug("没有空闲设备，跳过创建")
        return False

    # 4. 获取空闲设备并重置环境
    device = scheduler.device_pool.acquire()
    if not device:
        return False

    # 【关键修复】检查设备是否正被某个账号的任务占用
    if device.current_account_id is not None:
        logger.debug(
            f"设备 {device.address} 正被账号 {device.current_account_id} 占用，跳过创建"
        )
        scheduler.device_pool.release(device)
        return False

    # 标记设备正在创建账号
    device.is_creating_account = True

    try:
        logger.info(f"准备创建新账号，重置设备 {device.address} 环境")

        # 初始化 ADB 并重置环境
        from ptcgp_auto_v2.infra.adb import AdbController
        from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
        from ptcgp_auto_v2.infra.account_syncer import AccountSyncer
        from ptcgp_auto_v2.config.settings import get_settings

        settings = get_settings()

        adb = AdbController(device.address)
        if not adb.connect():
            logger.warning(f"无法连接设备 {device.address}")
            return False

        try:
            switcher = AccountSwitcher(adb)
            switcher.reset_game_environment()

            # 重启游戏，进入新账号创建流程
            adb.restart_app(settings.app_package)
            logger.info(f"设备 {device.address} 已重置并重启游戏，等待新账号创建")

            # 断开ADB连接，让游戏完全重启
            adb.disconnect()
            logger.debug("断开ADB连接，等待游戏重启完成")

        except Exception as e:
            logger.exception(f"重置设备环境失败: {e}")
            return False

        # 重启后等待8秒让游戏启动
        logger.debug("等待8秒让游戏完成初始启动...")
        time.sleep(8)

        # 循环尝试提取新账号信息（总共30秒，每5秒尝试一次）
        new_account = None
        for attempt in range(6):
            logger.debug(f"第 {attempt + 1}/6 次尝试提取账号信息...")

            # 每次重新连接ADB
            fresh_adb = AdbController(device.address)
            if not fresh_adb.connect():
                logger.warning(f"第 {attempt + 1} 次尝试：无法连接设备，5秒后重试")
                time.sleep(5)
                continue

            try:
                # 创建syncer并获取当前账号（会提取并自动创建新账号）
                syncer = AccountSyncer(fresh_adb)
                account = syncer.get_current_account()

                if account and account.id:
                    logger.info(f"获取到账号: {account.game_id}")

                    # 检查是否为新创建的账号（通过init_account任务判断）
                    from ptcgp_auto_v2.db.repositories import TaskInstanceRepository

                    task_repo = TaskInstanceRepository()
                    init_task = task_repo.get_by_account_and_type(
                        account.id, "init_account"
                    )

                    if init_task:
                        # 有init_task，说明是新创建的账号
                        logger.info(
                            f"发现新账号！Player ID: {account.game_id}, "
                            f"已创建init_account任务 (任务ID: {init_task.id})"
                        )
                        new_account = account
                        break
                    else:
                        # 没有init_task，说明是已存在的账号
                        logger.debug(
                            f"账号 {account.game_id} 已存在于数据库且无init_task，继续等待..."
                        )
                else:
                    logger.debug(
                        f"第 {attempt + 1} 次尝试：未获取到账号信息，5秒后重试"
                    )

            except Exception as e:
                logger.warning(f"第 {attempt + 1} 次尝试提取账号失败: {e}")
            finally:
                fresh_adb.disconnect()

            # 等待5秒后下次尝试
            if attempt < 5:  # 最后一次不需要等待
                time.sleep(5)

        if new_account:
            logger.info(f"新账号创建流程完成，账号ID: {new_account.game_id}")
            return True
        else:
            logger.warning("30秒内未能成功提取新账号信息，将在下次调度时重试")
            return False

    except Exception as e:
        logger.exception(f"触发新账号创建失败: {e}")
        return False
    finally:
        # 取消设备创建标记并归还
        device.is_creating_account = False
        scheduler.device_pool.release(device)
