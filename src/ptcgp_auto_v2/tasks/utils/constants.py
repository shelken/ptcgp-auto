# -*- coding: utf-8 -*-
"""
任务公共常量

基于 1080x1920 分辨率的基准像素值。
"""

# ============================================================
# 好友列表相关
# ============================================================
BASE_FRIEND_SCROLL_DISTANCE_Y = 520  # 好友列表单次上滑距离
BASE_FRIEND_ROW_THRESHOLD_Y = 150  # 同一行元素 Y 轴容差（考虑 OCR 抖动）
MAX_FRIEND_SCROLL_ROUNDS = 8  # 好友列表最大滑动轮数
MAX_FRIEND_STABLE_ROUNDS = 3  # 好友列表连续不变最大轮数
MAX_FRIEND_PROFILE_READ_ROUNDS = 3  # 好友详情读取 friend_id 最大重试轮数

# ============================================================
# 卡牌扫描相关
# ============================================================
BASE_CARD_SCROLL_DISTANCE_Y = 500  # 选卡列表单次上滑距离
MAX_CARD_STABLE_ROUNDS = 3  # 卡牌扫描连续不变最大轮数
BASE_PACK_RESULT_SCROLL_DISTANCE_Y = 320  # 10包结果页滚动距离，对齐 wonder_pick
PACK_RESULT_SCROLL_SWIPE_STEPS = 8  # 10包结果页滚动步数，对齐 wonder_pick
