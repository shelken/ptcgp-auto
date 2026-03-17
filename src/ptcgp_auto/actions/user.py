"""用户信息相关动作模块"""

import re
import time
from typing import Dict, Optional, Tuple

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)


class UserActions:
    """用户信息获取处理 - 作为状态机的动作处理器"""

    def __init__(self, adb, recognizer, state):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state

    def extract_user_info(self, screenshot, match_info: Dict):
        """从用户信息弹窗提取用户名和朋友ID并保存

        OCR 结果示例：
        "您的玩家資訊"@(536,930) - 标题
        "skn4"@(539,1026) - 用户名
        "朋友ID"@(540,1104) - 标签
        "8529-4131-7319-7882"@(545,1168) - 朋友ID
        """
        ocr_results = match_info.get("ocr_results", [])

        username, friend_id = self._parse_user_info(ocr_results)

        if username and friend_id:
            self.state.set_user_info(username, friend_id)
            # 返回上一页
            logger.info("  -> 用户信息已保存，返回")
            self.adb.back()
        else:
            logger.error(f"  -> 提取失败: username={username}, friend_id={friend_id}")
            self.adb.back()

    def click_add_friends(self, screenshot, match_info: Dict):
        """在朋友列表页面点击添加朋友图标"""
        # 如果已有用户信息，点击关闭按钮返回社群页面
        if self.state.has_user_info():
            close_box = self.recognizer.find_template(
                screenshot, "btn_close", threshold=0.7
            )
            if close_box:
                logger.info("  -> 点击关闭按钮")
                self.adb.tap_center(close_box)
            return

        # 查找并点击添加朋友图标
        add_friends_box = self.recognizer.find_template(
            screenshot, "icon_add_friends", threshold=0.7
        )
        if add_friends_box:
            logger.info("  -> 点击添加朋友图标")
            self.adb.tap_center(add_friends_box)
        else:
            logger.error("  -> 未找到添加朋友图标")

    def click_friends_tab(self, screenshot, match_info: Dict):
        """在社群页面点击朋友标签"""
        # 如果已有用户信息，点击对战图标回到主流程
        if self.state.has_user_info():
            logger.info("  -> 已有用户信息，点击对战图标")
            self._click_battle_icon(screenshot)
            return

        ocr_results = match_info.get("ocr_results", [])

        # 查找并点击"朋友"标签
        for item in ocr_results:
            text = item["text"].strip()
            # 精确匹配"朋友"，排除"朋友ID"、"朋友數"等
            if text == "朋友" or text == "好友":
                logger.info(f"  -> 点击: {text}")
                self.adb.tap_center(item["box"])
                return

        logger.info("  -> 未找到朋友标签，点击对战图标")
        self._click_battle_icon(screenshot)

    def _click_battle_icon(self, screenshot):
        """点击底部对战图标"""
        battle_box = self.recognizer.find_template(
            screenshot, "icon_battle", threshold=0.7
        )
        if battle_box:
            self.adb.tap_center(battle_box)
        else:
            logger.error("  -> 未找到对战图标")

    def _parse_user_info(self, ocr_results) -> Tuple[Optional[str], Optional[str]]:
        """解析 OCR 结果提取用户名和朋友ID"""
        username = None
        friend_id = None

        # 朋友 ID 格式：XXXX-XXXX-XXXX-XXXX（4组4位数字）
        friend_id_pattern = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}")

        # 提取朋友 ID
        for item in ocr_results:
            text = item["text"].strip()
            match = friend_id_pattern.search(text)
            if match:
                friend_id = match.group()
                break

        # 找标题和朋友ID标签的 Y 坐标
        friend_id_label_y = None
        title_y = None

        for item in ocr_results:
            text = item["text"].strip()
            y = item["box"][1]  # top y

            if "朋友ID" in text or "朋友 ID" in text or "Friend ID" in text:
                friend_id_label_y = y
            if "玩家資訊" in text or "玩家资讯" in text or "Player Info" in text:
                title_y = y

        # 查找用户名：在标题下方、朋友ID标签上方的文本
        if title_y is not None:
            candidates = []
            for item in ocr_results:
                text = item["text"].strip()
                y = item["box"][1]

                # 排除已知标签和 ID
                skip_patterns = [
                    "玩家資訊",
                    "玩家资讯",
                    "Player Info",
                    "朋友ID",
                    "朋友 ID",
                    "Friend ID",
                    "您的",
                    "Your",
                    "搜尋",
                    "輸入",
                    "僅限",
                ]
                if any(skip in text for skip in skip_patterns):
                    continue
                if friend_id_pattern.search(text):
                    continue
                # 排除单字符（可能是噪声）
                if len(text) <= 1:
                    continue

                # 在标题下方
                if y > title_y:
                    # 如果有朋友ID标签，必须在其上方
                    if friend_id_label_y is None or y < friend_id_label_y:
                        candidates.append((y, text))

            # 取最靠近标题的候选
            if candidates:
                candidates.sort(key=lambda x: x[0])
                username = candidates[0][1]

        if username and friend_id:
            logger.info(f"  -> 提取成功: {username} / {friend_id}")

        return username, friend_id


def fetch_user_info_via_ui(
    adb,
    recognizer,
    state,
    page_detector,
    action_handler,
    allow_restart: bool = False,
    max_steps: int = 120,
    max_stuck_steps: int = 8,
) -> bool:
    """通过 UI 流程获取用户信息"""
    logger.info("正在获取用户信息...")

    step = 0
    stuck_steps = 0
    last_page = None

    while not state.has_user_info() and step < max_steps:
        step += 1
        screenshot = adb.screenshot()
        if not screenshot:
            time.sleep(1)
            continue

        page_name, page_info, match_info = page_detector.detect(screenshot)
        if not page_name:
            time.sleep(1)
            continue

        if page_name == last_page:
            stuck_steps += 1
        else:
            stuck_steps = 0
        last_page = page_name

        if page_name == "battle_in_progress":
            logger.info("  -> 对战中，等待结束后再获取用户信息")
            time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)
            continue

        if allow_restart and stuck_steps >= max_stuck_steps:
            _restart_game(adb)
            stuck_steps = 0
            last_page = None
            time.sleep(3)
            continue

        logger.debug(f"  [{page_name}]")

        match_info["page_info"] = page_info

        if page_name == "user_info_popup":
            action_handler.execute("extract_user_info", screenshot, match_info)
            break

        if page_name == "friends_list":
            action_handler.execute("click_add_friends", screenshot, match_info)
        elif page_name == "community_page":
            action_handler.execute("click_friends_tab", screenshot, match_info)
        elif page_name == "game_home_main":
            box = recognizer.find_template(screenshot, "icon_community", threshold=0.7)
            if box:
                logger.debug("  -> 点击社群图标")
                adb.tap_center(box)
            else:
                adb.back()
        elif page_name in ("_main_page", "game_open_page"):
            action_handler.execute("click_identifier", screenshot, match_info)
        else:
            box = recognizer.find_template(screenshot, "icon_community", threshold=0.7)
            if box:
                logger.debug("  -> 点击社群图标")
                adb.tap_center(box)
            else:
                adb.back()

        time.sleep(config.WAIT_PAGE_TRANSITION)

    if state.has_user_info():
        logger.info("用户信息获取完成")
        return True

    logger.error("用户信息获取失败")
    return False


def _restart_game(adb):
    """重启游戏应用"""
    from ptcgp_auto.config import PTCGP_MAIN_ACTIVITY

    logger.warning("  -> 尝试重启游戏")
    adb.force_stop_app(config.PTCGP_PACKAGE_NAME)
    adb.shell(f"am start -n {PTCGP_MAIN_ACTIVITY}")
