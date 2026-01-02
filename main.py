"""
PTCGP 单人对战自动化脚本 - 主入口
"""

import time
import sys
from pathlib import Path

import config
from adb_controller import get_controller, AdbController
from recognizer import get_recognizer, Recognizer


class PTCGPAuto:
    """PTCGP 单人对战自动化"""

    def __init__(self):
        self.adb = get_controller()
        self.recognizer = get_recognizer()

    def start(self):
        """启动自动化"""
        print("=" * 50)
        print("PTCGP 单人对战自动化脚本")
        print("=" * 50)

        # 连接 ADB
        if not self.adb.connect():
            print("无法连接到模拟器，请检查 ADB 配置")
            return False

        print("\n开始自动化流程...")
        print("提示: 请确保游戏已经在单人对战界面\n")

        try:
            self.run_main_loop()
        except KeyboardInterrupt:
            print("\n用户中断，退出...")
        except Exception as e:
            print(f"\n发生错误: {e}")
            if config.DEBUG:
                import traceback
                traceback.print_exc()
        finally:
            self.adb.disconnect()

        return True

    def run_main_loop(self):
        """主循环 - 遍历所有等级"""
        for level in config.BATTLE_LEVELS:
            print(f"\n{'='*30}")
            print(f"检查等级: {level}")
            print(f"{'='*30}")

            if not self.process_level(level):
                print(f"等级 {level} 已完成或无法进入，跳过")
                continue

        print("\n所有等级处理完毕!")

    def process_level(self, level_name: str) -> bool:
        """处理单个等级

        Args:
            level_name: 等级名称（初级/中级/高级/精英）

        Returns:
            是否成功处理
        """
        screenshot = self.adb.screenshot()
        if not screenshot:
            return False

        # 检查是否已完成
        status = self.recognizer.check_complete_status(screenshot)
        if status['complete']:
            print(f"{level_name} 已全部完成 (Complete)")
            return False

        # 查找并点击等级入口
        level_box = self.recognizer.find_text(screenshot, level_name)
        if not level_box:
            print(f"未找到 {level_name} 入口")
            return False

        self.adb.tap_center(level_box)
        time.sleep(config.WAIT_PAGE_TRANSITION)

        # 处理当前卡包的所有牌组
        self.process_current_pack()

        # 处理扩充组
        self.process_expansion_packs()

        # 返回上一级
        self.adb.back()
        time.sleep(config.WAIT_PAGE_TRANSITION)

        return True

    def process_current_pack(self):
        """处理当前卡包的所有牌组"""
        print("处理当前卡包...")

        while True:
            screenshot = self.adb.screenshot()
            if not screenshot:
                break

            # 查找可点击的牌组（非 CLEAR 状态）
            # 这里需要根据实际界面调整识别逻辑
            deck_box = self.find_available_deck(screenshot)
            if not deck_box:
                print("当前卡包已无可挑战的牌组")
                break

            # 点击牌组
            self.adb.tap_center(deck_box)
            time.sleep(config.WAIT_PAGE_TRANSITION)

            # 开始对战
            if not self.start_battle():
                # 如果无法开始对战，返回
                self.adb.back()
                time.sleep(config.WAIT_PAGE_TRANSITION)
                break

            # 等待对战结束
            self.wait_battle_end()

            # 点击继续
            self.click_continue()

            # 等待回到牌组列表
            time.sleep(config.WAIT_PAGE_TRANSITION)

    def process_expansion_packs(self):
        """处理扩充组中的历史卡包"""
        print("检查扩充组...")

        screenshot = self.adb.screenshot()
        if not screenshot:
            return

        # 查找并点击"扩充组"按钮
        expansion_box = self.recognizer.find_text(screenshot, "扩充组")
        if not expansion_box:
            # 尝试英文
            expansion_box = self.recognizer.find_text(screenshot, "Expansion")
        if not expansion_box:
            print("未找到扩充组入口")
            return

        self.adb.tap_center(expansion_box)
        time.sleep(config.WAIT_PAGE_TRANSITION)

        # 处理 A/B 系列
        for series in ["A", "B"]:
            self.process_series(series)

        # 返回
        self.adb.back()
        time.sleep(config.WAIT_PAGE_TRANSITION)

    def process_series(self, series_name: str):
        """处理某个系列（A/B）的所有卡包"""
        print(f"检查 {series_name} 系列...")

        screenshot = self.adb.screenshot()
        if not screenshot:
            return

        # 查找系列标签
        series_box = self.recognizer.find_text(screenshot, series_name)
        if not series_box:
            print(f"未找到 {series_name} 系列")
            return

        self.adb.tap_center(series_box)
        time.sleep(config.WAIT_PAGE_TRANSITION)

        # 遍历该系列的所有卡包
        self.process_all_packs_in_series()

    def process_all_packs_in_series(self):
        """处理当前系列的所有卡包"""
        max_scrolls = 10  # 最大滑动次数，防止无限循环

        for _ in range(max_scrolls):
            screenshot = self.adb.screenshot()
            if not screenshot:
                break

            # 查找未完成的卡包（非 CLEAR）
            pack_box = self.find_available_pack(screenshot)
            if not pack_box:
                # 尝试向下滑动查看更多
                self.adb.swipe_up()
                time.sleep(config.WAIT_PAGE_TRANSITION)

                # 再次检查
                screenshot = self.adb.screenshot()
                pack_box = self.find_available_pack(screenshot)
                if not pack_box:
                    print("当前系列已无可挑战的卡包")
                    break

            # 点击卡包
            self.adb.tap_center(pack_box)
            time.sleep(config.WAIT_PAGE_TRANSITION)

            # 处理该卡包的所有牌组
            self.process_current_pack()

            # 返回系列列表
            self.adb.back()
            time.sleep(config.WAIT_PAGE_TRANSITION)

    def find_available_deck(self, screenshot) -> tuple:
        """查找可挑战的牌组

        Returns:
            牌组区域坐标，未找到返回 None
        """
        # TODO: 根据实际界面实现
        # 这里需要识别牌组列表，排除已 CLEAR 的
        # 暂时使用模板匹配查找牌组按钮
        deck_box = self.recognizer.find_template(screenshot, "btn_deck")
        return deck_box

    def find_available_pack(self, screenshot) -> tuple:
        """查找可挑战的卡包（非 CLEAR）

        Returns:
            卡包区域坐标，未找到返回 None
        """
        # TODO: 根据实际界面实现
        # 需要识别卡包列表，找到显示数字（如 3/5）而非 CLEAR 的
        ocr_results = self.recognizer.ocr_full_screen(screenshot)

        for item in ocr_results:
            text = item['text']
            # 查找进度格式 "X/Y"
            if '/' in text and 'CLEAR' not in text.upper():
                import re
                if re.match(r'\d+\s*/\s*\d+', text):
                    return item['box']

        return None

    def start_battle(self) -> bool:
        """开始对战

        Returns:
            是否成功开始
        """
        screenshot = self.adb.screenshot()
        if not screenshot:
            return False

        # 查找"对战"按钮
        battle_btn = self.recognizer.find_template(screenshot, "btn_battle")
        if not battle_btn:
            battle_btn = self.recognizer.find_text(screenshot, "对战")
        if not battle_btn:
            battle_btn = self.recognizer.find_text(screenshot, "Battle")

        if not battle_btn:
            print("未找到对战按钮")
            return False

        self.adb.tap_center(battle_btn)
        time.sleep(config.WAIT_PAGE_TRANSITION)
        return True

    def wait_battle_end(self):
        """等待对战结束"""
        print("等待对战结束...")

        # 等待出现"点击来继续"或类似提示
        found = self.recognizer.wait_for_text(
            self.adb,
            "继续",  # 或 "Tap to continue"
            timeout=config.WAIT_BATTLE_TIMEOUT,
            check_interval=config.WAIT_BATTLE_CHECK_INTERVAL
        )

        if not found:
            # 尝试其他可能的结束提示
            found = self.recognizer.wait_for_text(
                self.adb,
                "continue",
                timeout=30,
                check_interval=config.WAIT_BATTLE_CHECK_INTERVAL
            )

        if found:
            print("对战结束!")
        else:
            print("等待对战结束超时")

    def click_continue(self):
        """点击继续按钮"""
        screenshot = self.adb.screenshot()
        if not screenshot:
            return

        # 尝试多种方式查找继续按钮
        continue_btn = self.recognizer.find_text(screenshot, "继续")
        if not continue_btn:
            continue_btn = self.recognizer.find_text(screenshot, "continue")
        if not continue_btn:
            continue_btn = self.recognizer.find_template(screenshot, "btn_continue")

        if continue_btn:
            self.adb.tap_center(continue_btn)
        else:
            # 如果找不到，点击屏幕中央
            self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

        time.sleep(config.WAIT_PAGE_TRANSITION)


def main():
    """主入口"""
    auto = PTCGPAuto()
    auto.start()


if __name__ == "__main__":
    main()
