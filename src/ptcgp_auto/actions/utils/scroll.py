"""滚动查找工具"""


class ScrollHelper:
    """滚动查找辅助类"""

    def __init__(self, adb, recognizer, max_attempts: int = 10, ratio: float = 0.21, delay: float = 0.8):
        """
        Args:
            adb: AdbController 实例
            recognizer: Recognizer 实例
            max_attempts: 最大滑动次数
            ratio: 滑动距离占屏幕高度的比例（默认 0.21 约等于 1920 下的 400px）
            delay: 滑动后等待时间
        """
        self.adb = adb
        self.recognizer = recognizer
        self.max_attempts = max_attempts
        self.ratio = ratio
        self.delay = delay
