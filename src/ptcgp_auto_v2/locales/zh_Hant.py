# -*- coding: utf-8 -*-
"""
繁体中文文本配置（仅开包相关）
"""

TEXT_PATTERNS = {
    # 开包入口
    "pack_entry": ["卡包", "擴充包", "扩充包"],
    # 系列切换
    "series": {
        "A": ["A系列"],
        "B": ["B系列"],
    },
    # 页面识别文本
    "game_home_main": ["商店/兌換處", "得卡挑戰"],
    "pack_series_select": ["選擇擴充組"],
    "pack_list": ["提供比例", "其他擴充包"],
    "pack_list_exclude": ["開封", "開封10包"],
    "open_pack": ["開封"],
    "open_pack_exclude": ["開封10包", "開封1包", "橫向滑動來開封"],
    "pack_hourglass_popup": [
        "要使用道具",
        "縮短開封卡牌包的等待時間嗎",
        "使用道具立刻開封擴充包",
    ],
    "pack_paid_detail": ["開封1包", "開封10包", "使用寶可金塊縮短時間"],
    "pack_opening_select": ["點擊想開封的擴充包"],
    "pack_opening_swipe": ["橫向滑動來開封"],
    "pack_opening_result": ["開封結果", "開包點數", "閃亮沙子"],
    "pack_card_register": ["向上輕滑卡牌"],
    "pack_collection_result": ["繼續"],
    "pack_collection_exclude": ["開封結果", "點擊來繼續", "點擊以繼續"],
    # 个人资料页
    "profile_page": ["朋友ID"],
    "profile_exclude": ["朋友ID", "Lv.", "戰績", "勳章", "請多多指教", "編輯", "設定", "登出"],
    # 通用页面
    "popup_ok": ["OK"],
    "network_error_popup": ["再試一次"],
    "continue_button": ["繼續"],
    "tap_to_continue": ["點擊來繼續", "點擊以繼續", "点击继续"],
    "game_open_page": ["點擊畫面開始遊戲"],
    "main_page": ["Pokémon Trad"],
    "close_app_popup": ["关闭应用", "应用信息"],
    "auth_again": ["再度執行認證"],
    # 通用按钮
    "confirm": ["確認", "确认", "OK"],
    "continue": ["繼續", "继续", "Continue"],
    "back_button": ["返回", "返回上一頁", "返回上一页", "Back"],
    "close_button": ["×"],
    "long_press": ["長按", "長按以跳過", "長按開封"],
    "open_pack_1": ["開封1包"],
    # ============================================================
    # 任务奖励领取相关
    # ============================================================
    # 任务奖励页面识别：通过 Tab 栏识别（每日/圖鑑/牌組/掉落）
    "rewards_page_tabs": ["每日", "圖鑑", "牌組", "掉落"],
    # Tab 名称（用于点击切换）
    "rewards_tab_daily": ["每日"],
    "rewards_tab_collection": ["圖鑑"],
    "rewards_tab_deck": ["牌組"],
    "rewards_tab_drop": ["掉落"],
    "rewards_tab_premium": ["特級"],
    # 可点击的领取按钮（按优先级排序：全部領取 > 領取 > 達成）
    "reward_claim_buttons": ["全部領取", "領取", "達成", "達成！"],
    # 奖励详情页面（点击領取后展示卡牌的页面，有報酬和達成按钮）
    "reward_detail_page": ["報酬", "達成！"],
    # 主题收藏入口/标题（任务页面底部入口 + 主题收藏页面标题）
    "theme_collection": ["主題收藏"],
    # ============================================================
    # 礼物盒领取相关
    # ============================================================
    # 礼物盒页面识别
    "gift_box_page": ["禮物盒"],
    # 无可领取提示（任务完成标志）
    "gift_empty": ["沒有可領取的道具"],
    # 可点击的领取按钮（按优先级排序：全部領取 > 領取）
    "gift_claim_buttons": ["全部領取", "領取"],
    # 领取纪录（用于过滤同行的领取 Tab 按钮）
    "gift_record": ["領取紀錄"],
    # 送出谢谢弹窗识别（朋友礼物）
    "gift_send_thanks": ["要送出「謝謝！」嗎"],
    # 谢谢按钮
    "gift_thanks_button": ["謝謝！"],
}
