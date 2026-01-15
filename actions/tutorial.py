"""教程解锁动作 - 处理新手账号单人对战解锁"""

import time
from typing import Dict

import config
from logger import get_logger

logger = get_logger(__name__)
from adb_controller import AdbController
from recognizer import Recognizer


class TutorialRunner:
    """教程解锁子流程 - 独立循环直到完成"""

    def __init__(self, adb: AdbController, recognizer: Recognizer):
        self.adb = adb
        self.recognizer = recognizer
        self.unknown_count = 0
        self.max_unknown = 5
        # 状态：是否已扫描过列表
        self.list_scanned = False
        self.found_shalou = False

    def run(self):
        """运行教程解锁流程，直到完成或退出"""
        logger.info("  [教程] 进入教程解锁流程")

        while True:
            time.sleep(1)
            screenshot = self.adb.screenshot()
            if not screenshot:
                continue

            state, ocr_results = self._detect_state(screenshot)
            logger.info(f"  [教程] 状态: {state}")

            if state == "tutorial_list":
                self._on_tutorial_list(screenshot)
            elif state == "in_tutorial":
                self._on_in_tutorial(screenshot, ocr_results)
            elif state == "need_scroll":
                self.adb.swipe_up()
            elif state == "need_scroll_up":
                self.adb.swipe_down()
            elif state == "complete":
                logger.info("  [教程] 00-06 全部完成")
                self.adb.back()
                break
            elif state == "exited":
                logger.info("  [教程] 已退出教程流程")
                break

    def _detect_state(self, screenshot):
        """检测当前教程状态

        Returns:
            (state, ocr_results) 元组
        """
        ocr_results = self.recognizer.ocr_full_screen(screenshot)
        ocr_texts = [item["text"] for item in ocr_results]
        all_text = " ".join(ocr_texts)

        # 1. 检测是否退出到其他页面
        if "與他人對戰" in all_text:
            return "exited", ocr_results
        if "商店/兌換處" in all_text or "得卡挑戰" in all_text:
            return "exited", ocr_results

        # 1.5 优先检测弹窗（OK 按钮、关闭按钮等）
        # 这类弹窗需要立即处理，不能被误判为 need_scroll
        if any(item["text"] == "OK" for item in ocr_results):
            return "in_tutorial", ocr_results
        close_box = self.recognizer.find_template(screenshot, "btn_close")
        if close_box:
            return "in_tutorial", ocr_results

        # 2. 检测是否在玩法列表
        shalou_boxes = self.recognizer.find_all_templates(screenshot, "wanfa_shalou")
        has_wanfa_title = "玩法" in all_text
        has_06 = any("06" in t for t in ocr_texts)

        if shalou_boxes:
            # 有沙漏 = 有未完成教程
            self.unknown_count = 0
            self.found_shalou = True
            return "tutorial_list", ocr_results
        elif has_wanfa_title or self.list_scanned:
            # 在玩法列表但没沙漏
            self.unknown_count = 0
            if has_06:
                # 看到 06 且没沙漏
                if self.found_shalou:
                    # 之前找到过沙漏，说明刚完成一个，需要滚回顶部
                    self.found_shalou = False
                    self.list_scanned = False
                    return "need_scroll_up", ocr_results
                else:
                    # 全部完成
                    return "complete", ocr_results
            else:
                # 没看到 06 = 需要滚动
                self.list_scanned = True
                return "need_scroll", ocr_results

        # 3. 检测是否在教程中（有教程相关文字）
        tutorial_hints = ["對戰對手", "派出手牌", "結束回合", "使用招式", "附加能量"]
        if any(hint in all_text for hint in tutorial_hints):
            self.unknown_count = 0
            return "in_tutorial", ocr_results

        # 4. 未知状态
        self.unknown_count += 1
        if self.unknown_count >= self.max_unknown:
            return "exited", ocr_results
        return "in_tutorial", ocr_results

    def _on_tutorial_list(self, screenshot):
        """在玩法列表 -> 点击最上面的未完成教程"""
        shalou_boxes = self.recognizer.find_all_templates(screenshot, "wanfa_shalou")
        if shalou_boxes:
            shalou_boxes.sort(key=lambda box: box[1])
            top_shalou = shalou_boxes[0]
            logger.info(f"  [教程] 发现 {len(shalou_boxes)} 个未完成，点击最上面的")
            self.adb.tap_center(top_shalou)

    def _on_in_tutorial(self, screenshot, ocr_results):
        """在教程中 -> 根据提示执行操作"""
        all_text = " ".join([item["text"] for item in ocr_results])

        # 0. 检测 OK 弹窗（教程完成奖励等）
        for item in ocr_results:
            if item["text"] == "OK":
                logger.info("  [教程] 检测到 OK 弹窗，点击")
                self.adb.tap_center(item["box"])
                return

        # 0.1 检测关闭按钮
        close_box = self.recognizer.find_template(screenshot, "btn_close")
        if close_box:
            logger.info("  [教程] 检测到关闭按钮，点击")
            self.adb.tap_center(close_box)
            return

        # 0.2 检测 "長按" 文字 -> 在手指位置长按
        if "長按" in all_text:
            # hand_down 特殊处理：用手指 x + 固定 y（卡牌位置）
            hand_down_box = self.recognizer.find_template(screenshot, "hand_down")
            if hand_down_box:
                hand_center_x = (hand_down_box[0] + hand_down_box[2]) // 2
                card_y = int(config.SCREEN_HEIGHT * 0.92)
                logger.info(f"  [教程] 检测到長按+hand_down，在 ({hand_center_x},{card_y}) 长按")
                self.adb.long_press(hand_center_x, card_y, duration=1500)
                return

            # 找到長按文字位置
            long_press_item = None
            for item in ocr_results:
                if "長按" in item["text"]:
                    long_press_item = item
                    break

            if long_press_item:
                long_press_x = (long_press_item["box"][0] + long_press_item["box"][2]) // 2
                long_press_y = (long_press_item["box"][1] + long_press_item["box"][3]) // 2

                # 其他手指模板：取長按x + (長按y和手指y的中心)
                for template in ["hand_up_left", "hand_up", "hand_up_right"]:
                    hand_box = self.recognizer.find_template(screenshot, template)
                    if hand_box:
                        hand_center_y = (hand_box[1] + hand_box[3]) // 2
                        target_y = (long_press_y + hand_center_y) // 2
                        logger.info(f"  [教程] 检测到長按+{template}，在 ({long_press_x},{target_y}) 长按")
                        self.adb.long_press(long_press_x, target_y, duration=1500)
                        return

                # 没找到手指，在長按文字位置长按
                logger.info("  [教程] 检测到長按文字，执行长按")
                self.adb.long_press_center(long_press_item["box"], duration=1500)
                return

        # 1. 检测 blue_circle 模板 -> 优先点击
        blue_circle_box = self.recognizer.find_template(screenshot, "blue_circle")
        if blue_circle_box:
            logger.info("  [教程] 检测到蓝色圆圈，点击")
            self.adb.tap_center(blue_circle_box)
            return

        # 2. 检测 hand_up_left 模板
        hand_left_box = self.recognizer.find_template(screenshot, "hand_up_left", threshold=0.7)
        if hand_left_box:
            # 判断是点击技能、拖动能量还是拖动进化
            # 如果有 "撤退" 文字，说明在卡片详情页，需要点击技能
            if "撤退" in all_text:
                logger.info("  [教程] 检测到左侧手指+撤退，点击技能")
                self.adb.tap_center(hand_left_box)
            else:
                # 高频检测手指位置
                end_x = config.SCREEN_WIDTH // 2
                end_y = int(config.SCREEN_HEIGHT * 0.55)

                # 如果有 "請選擇" 提示，优先点击
                if "請選擇" in all_text:
                    logger.info("  [教程] 检测到選擇提示，点击")
                    self.adb.tap_center(hand_left_box)
                    return

                # 如果有 "放置" 或 "配置" 提示，优先拖动卡牌
                if "放置" in all_text or "配置" in all_text:
                    hand_center_x = (hand_left_box[0] + hand_left_box[2]) // 2
                    start_x = hand_center_x
                    start_y = int(config.SCREEN_HEIGHT * 0.92)
                    end_x = config.SCREEN_WIDTH // 2
                    end_y = int(config.SCREEN_HEIGHT * 0.55)
                    logger.info(f"  [教程] 检测到放置提示，拖动卡牌 ({start_x},{start_y}) -> ({end_x},{end_y})")
                    self.adb.drag(start_x, start_y, end_x, end_y, duration=500)
                    return

                # 连续检测5次手指位置
                right_bottom_count = 0  # 右下角计数（拖能量）
                bottom_count = 0  # 底部计数（拖卡牌）
                for _ in range(5):
                    check_screenshot = self.adb.screenshot()
                    if check_screenshot:
                        hand = self.recognizer.find_template(check_screenshot, "hand_up_left", threshold=0.7)
                        if hand:
                            hx = (hand[0] + hand[2]) // 2
                            hy = (hand[1] + hand[3]) // 2
                            if hx > config.SCREEN_WIDTH * 0.7 and hy > config.SCREEN_HEIGHT * 0.7:
                                right_bottom_count += 1
                            elif hy > config.SCREEN_HEIGHT * 0.8:
                                bottom_count += 1
                    time.sleep(0.1)

                if right_bottom_count >= 2:
                    # 多次在右下角：拖动能量
                    start_x = int(config.SCREEN_WIDTH * 0.9)
                    start_y = int(config.SCREEN_HEIGHT * 0.92)
                    logger.info(f"  [教程] 检测到右下角手指，拖动能量 ({start_x},{start_y}) -> ({end_x},{end_y})")
                    self.adb.drag(start_x, start_y, end_x, end_y, duration=500)
                elif bottom_count >= 3:
                    # 多次在底部：拖动卡牌
                    hand_center_x = (hand_left_box[0] + hand_left_box[2]) // 2
                    start_x = hand_center_x
                    start_y = int(config.SCREEN_HEIGHT * 0.92)
                    logger.info(f"  [教程] 检测到底部手指，拖动卡牌 ({start_x},{start_y}) -> ({end_x},{end_y})")
                    self.adb.drag(start_x, start_y, end_x, end_y, duration=500)
                else:
                    # 默认：点击
                    logger.info("  [教程] 检测到手指，点击")
                    self.adb.tap_center(hand_left_box)
            return

        # 3. 检测 hand_up_right 模板 -> 点击对应按钮
        hand_right_box = self.recognizer.find_template(screenshot, "hand_up_right")
        if hand_right_box:
            # 查找右侧按钮文字并点击（結束回合、準備完畢等）
            # 只匹配屏幕右半部分的按钮，避免点到提示文字
            right_buttons = ["結束回合", "回合", "準備完畢"]
            screen_center_x = config.SCREEN_WIDTH // 2
            for item in ocr_results:
                box_center_x = (item["box"][0] + item["box"][2]) // 2
                if box_center_x > screen_center_x and any(btn in item["text"] for btn in right_buttons):
                    logger.info(f"  [教程] 检测到右侧手指，点击 {item['text']}")
                    self.adb.tap_center(item["box"])
                    return
            # 没找到文字，点击手指位置
            logger.info("  [教程] 检测到右侧手指，点击手指位置")
            self.adb.tap_center(hand_right_box)
            return

        # 3. 检测 hand_up 模板 -> 点击手指位置
        hand_box = self.recognizer.find_template(screenshot, "hand_up")
        if hand_box:
            logger.info("  [教程] 检测到手指引导，点击")
            self.adb.tap_center(hand_box)
            return

        # 3. 没有手指模板，点击屏幕中心
        x = config.SCREEN_WIDTH // 2
        y = config.SCREEN_HEIGHT // 2
        self.adb.tap(x, y)


class TutorialActions:
    """教程相关动作处理"""

    def __init__(self, adb: AdbController, recognizer: Recognizer):
        self.adb = adb
        self.recognizer = recognizer

    def handle_tutorial_unlock(self, screenshot, match_info: Dict):
        """对战菜单检测到锁定 -> 点击玩法并进入教程子流程"""
        ocr_results = match_info.get("ocr_results", [])

        for item in ocr_results:
            if "玩法" in item["text"]:
                self.adb.tap_center(item["box"])
                logger.info("  -> 点击玩法按钮")
                time.sleep(config.WAIT_PAGE_TRANSITION)

                # 运行教程子流程
                runner = TutorialRunner(self.adb, self.recognizer)
                runner.run()
                return

        logger.error("  -> 未找到玩法按钮")

    def handle_tutorial_list(self, screenshot, match_info: Dict):
        """玩法列表页面 -> 直接进入教程子流程"""
        runner = TutorialRunner(self.adb, self.recognizer)
        runner.run()

    def handle_tutorial_step(self, screenshot, match_info: Dict):
        """教学步骤（已废弃，由 TutorialRunner 处理）"""
        pass
