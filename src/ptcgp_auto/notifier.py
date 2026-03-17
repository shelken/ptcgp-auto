"""
Notification module for PTCGP automation
Supports WeCom (WeChat Work) webhook and macOS sound alerts
"""

import json
import subprocess
from urllib import request

from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)


def send_wecom_notification(key: str, message: str) -> bool:
    """
    Send notification via WeCom (WeChat Work) webhook

    Args:
        key: Webhook key (the part after ?key= in the webhook URL)
        message: Message content to send

    Returns:
        True if successful, False otherwise
    """
    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    payload = {"msgtype": "text", "text": {"content": message}}

    try:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("errcode") == 0:
                logger.info("[Notify] WeCom notification sent")
                return True
            else:
                logger.error(
                    f"[Notify] WeCom error: {result.get('errmsg', 'Unknown error')}"
                )
                return False
    except Exception as e:
        logger.error(f"[Notify] Failed to send WeCom notification: {e}")
        return False


def play_sound() -> bool:
    """
    Play system alert sound on macOS

    Returns:
        True if successful, False otherwise
    """
    try:
        # Use macOS system sound (Glass is a common alert sound)
        subprocess.run(
            ["afplay", "/System/Library/Sounds/Glass.aiff"],
            check=True,
            capture_output=True,
        )
        logger.info("[Notify] Sound alert played")
        return True
    except subprocess.CalledProcessError:
        # Fallback: use osascript to trigger system beep
        try:
            subprocess.run(
                ["osascript", "-e", "beep 2"], check=True, capture_output=True
            )
            logger.info("[Notify] Sound alert played (beep)")
            return True
        except Exception as e:
            logger.error(f"[Notify] Failed to play sound: {e}")
            return False
    except FileNotFoundError:
        logger.error("[Notify] Sound playback not available (not macOS)")
        return False


def notify_unrecognized(
    key: str, sound: bool = True, port: int = None, username: str = None
) -> None:
    """
    Send notification for unrecognized screen state

    Args:
        key: WeCom webhook key
        sound: Whether to play sound alert
        port: ADB port number
        username: Username for identification
    """
    # 构建设备标识
    device_info = f"端口: {port}" if port else ""
    if username:
        device_info += f" | 用户: {username}" if device_info else f"用户: {username}"

    message = f"[PTCGP Auto] {device_info}\n界面无法识别，可能需要手动干预。"

    if key:
        send_wecom_notification(key, message)

    if sound:
        play_sound()


def notify_level_complete(
    key: str, level: str, sound: bool = True, port: int = None, username: str = None
) -> None:
    """
    发送等级完成通知

    Args:
        key: WeCom webhook key
        level: 完成的等级名称
        sound: 是否播放提示音
        port: ADB 端口
        username: 用户名
    """
    device_info = f"端口: {port}" if port else ""
    if username:
        device_info += f" | 用户: {username}" if device_info else f"用户: {username}"

    message = f"[PTCGP Auto] {device_info}\n✅ 等级 {level} 已完成！"

    if key:
        send_wecom_notification(key, message)

    if sound:
        play_sound()


def notify_completed(
    key: str, sound: bool = True, port: int = None, username: str = None
) -> None:
    """
    Send notification when all tasks are completed

    Args:
        key: WeCom webhook key
        sound: Whether to play sound alert
        port: ADB port number
        username: Username for identification
    """
    # 构建设备标识
    device_info = f"端口: {port}" if port else ""
    if username:
        device_info += f" | 用户: {username}" if device_info else f"用户: {username}"

    message = f"[PTCGP Auto] {device_info}\n🎉 所有分级对战任务已完成！"

    if key:
        send_wecom_notification(key, message)

    if sound:
        play_sound()


def notify_recovered(
    key: str, sound: bool = True, port: int = None, username: str = None
) -> None:
    """发送识别恢复通知

    Args:
        key: WeCom webhook key
        sound: 是否播放提示音
        port: ADB 端口
        username: 用户名
    """
    device_info = f"端口: {port}" if port else ""
    if username:
        device_info += f" | 用户: {username}" if device_info else f"用户: {username}"

    message = f"[PTCGP Auto] {device_info}\n✅ 界面识别已恢复正常"

    if key:
        send_wecom_notification(key, message)

    if sound:
        play_sound()


def notify_battle_started(
    key: str, level: str, sound: bool = True, port: int = None, username: str = None
) -> None:
    """发送对战开始通知

    Args:
        key: WeCom webhook key
        level: 当前等级
        sound: 是否播放提示音
        port: ADB 端口
        username: 用户名
    """
    device_info = f"端口: {port}" if port else ""
    if username:
        device_info += f" | 用户: {username}" if device_info else f"用户: {username}"

    message = f"[PTCGP Auto] {device_info}\n🎮 开始刷包 - 当前等级: {level}"

    if key:
        send_wecom_notification(key, message)

    if sound:
        play_sound()
