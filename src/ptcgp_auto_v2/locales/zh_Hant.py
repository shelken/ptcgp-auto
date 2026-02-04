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
    "game_home_main": ["商店", "得卡挑戰"],
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
    "pack_opening_select": ["點擊想開封的擴充包"],
    "pack_opening_swipe": ["橫向滑動來開封"],
    "pack_opening_result": ["開封結果", "開包點數", "閃亮沙子"],
    "pack_card_register": ["向上輕滑卡牌"],
    "pack_collection_result": ["繼續"],
    "pack_collection_exclude": ["開封結果", "點擊來繼續", "點擊以繼續"],
    # 个人资料页
    "profile_page": ["朋友ID"],
    "profile_exclude": [
        "朋友ID",
        "Lv.",
        "戰績",
        "勳章",
        "請多多指教",
        "編輯",
        "設定",
        "登出",
    ],
    # 社群页面
    "community_page": ["社群", "他人的收藏"],
    "community_exchange_btn": ["交換"],
    # 交换页面
    "exchange_page": ["交換卡牌", "設定", "紀錄"],
    "exchange_point_title": ["交換"],
    # 交换未解锁弹窗
    "exchange_locked_popup": ["開放條件", "距離開放還剩"],
    # 通用页面
    "popup_ok": ["OK", "ОК"],  # 支持英文OK和俄文ОК（西里尔字母）
    "text_cancel": ["取消"],
    "text_ok": ["OK", "ОК"],  # 支持英文OK和俄文ОК（西里尔字母）
    "text_retry": ["再試一次"],
    "text_x": ["x"],
    "text_task": ["任務"],
    "continue_button": ["繼續"],
    "tap_to_continue": ["點擊來繼續"],
    "game_open_page": ["點擊畫面開始遊戲"],
    "popup_game_launch_fail": ["啟動發生錯誤", "遊戲啟動失敗"],
    "popup_return_to_title_screen": ["回到標題畫面"],
    "popup_close_game": ["關閉應用程式嗎"],
    "popup_auth_again": ["再度執行認證"],
    "popup_network_error": ["再試一次"],
    "popup_clean_and_download": ["清除快取", "重新下載"],
    "error_code_103_011_05400": ["103-011-05400"],
    ## 游戏外
    "main_page": ["Pokémon Trad"],
    "close_app_popup": ["关闭应用", "应用信息"],
    "_to_home": ["首页", "重新加载"],
    "text_home": ["首页"],
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
    "rewards_tab_account_link": ["帳號連結"],
    "rewards_tab_premium": ["特級"],
    "rewards_tab_elite_deck": ["精英牌組"],
    "rewards_tab_convenient_cards": ["便利卡牌"],
    # 可点击的领取按钮（按优先级排序：全部領取 > 領取 > 達成）
    "reward_claim_buttons": ["全部領取", "領取", "達成", "達成！"],
    # 需要颜色检查的"全部領取"按钮（用于避免点击置灰按钮）
    "reward_claim_all": ["全部領取"],
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
    # 送出谢谢弹窗识别
    "popup_send_thanks": ["要送出「謝謝！」嗎"],
    # 谢谢按钮
    "thanks_button": ["謝謝！"],
    # ============================================================
    # 卡牌列表与筛选相关
    # ============================================================
    "card_page_own": ["自己的卡牌"],
    "card_filter_title": ["稀有度"],
    "card_filter_clear": ["清除"],
    "card_filter_no_target": ["沒有對象卡牌"],
    "card_sort_title": ["排序"],
    "card_sort_by_acquired": ["按卡牌獲得順序"],
    # ============================================================
    # 得卡挑战相关
    # ============================================================
    "card_challenge_title": ["得卡挑戰"],
    "card_challenge_get": ["GET!"],
    "card_challenge_remaining_plays": ["剩餘遊玩次數"],
    "card_challenge_recover": ["恢復"],
    "card_challenge_end_already": ["已挑戰"],
    "card_challenge_end_finished": ["已結束"],
    # ============================================================
    # 新账号初始化流程
    # ============================================================
    "init_select_country": ["選擇國家", "請選擇您居住的國家"],
    "init_country_btn": ["國家/地區"],  # 国家/地区选择按钮
    "init_year_btn": ["年"],  # 年份选择按钮
    "init_month_btn": ["月"],  # 月份选择按钮
    "init_month_2": ["2"],  # 月份 2
    "init_terms_privacy": ["使用條款", "隱私權政策"],
    "init_terms_btn": ["使用條款"],
    "init_privacy_btn": ["隱私權政策"],
    "init_data_use": ["關於資料使用"],
    "init_create_save": ["建立儲存資料"],
    "init_start_from_scratch": ["從頭開始"],
    "init_account_link": ["帳號連結"],
    "init_skip_link": ["現在不連結"],
    "init_set_nickname": ["請設定頭像和玩家名稱"],
    "init_nickname_title": ["玩家名稱"],
    "init_nickname_warning": ["請勿使用本名"],  # 昵称异常提示
    "init_confirm_settings": ["確定要使用此設定嗎"],
    "init_select_pack": ["請選擇喜歡的擴充包"],
    "init_decide": ["決定"],
    "init_swipe_open": ["橫向滑動來開封"],
    "init_next_step": ["下一步"],
    "init_mission": ["任務"],
    "init_open_pack": ["開封"],
    "init_enjoy": ["請好好享受", "隨意遊玩"],
    "init_tap_to_flip": ["點擊來翻開卡牌吧"],
    "init_select_favorite_card": ["選1張喜歡的卡牌吧"],
}
