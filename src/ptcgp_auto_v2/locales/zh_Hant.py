# -*- coding: utf-8 -*-
"""
繁体中文文本配置（仅开包相关）
"""

# 对战任务等级列表（从难到易）
BATTLE_LEVELS = ["精英", "高級", "中級", "初級"]

TEXT_PATTERNS = {
    # 开包入口
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
    "open_pack_exclude": ["橫向滑動來開封"],
    "open_pack_1": ["開封1包"],
    "open_pack_10": ["開封10包"],
    "use_item_confirm": ["要使用道具"],
    "pack_opening_select": ["點擊想開封的擴充包"],
    "pack_opening_swipe": ["橫向滑動來開封"],
    "pack_opening_multi_result": ["第1包"],
    "pack_opening_result": ["開封結果", "開包點數", "閃亮沙子"],
    "pack_card_register": ["向上輕滑卡牌"],
    "profile_page": ["朋友ID"],
    "profile_page_exclude": ["搜尋玩家"],  # 搜尋玩家 为搜索好友页面时也出现 朋友ID
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
    "community_page": ["他人的收藏"],
    "community_exchange_btn": ["交換"],
    # 更多菜单 / 持有物页面
    "more_menu_modal": ["商店", "禮物盒"],
    "more_menu_holdings": ["持有物"],
    "holdings_page": ["持有物", "寶可金塊（免費）"],
    "holdings_page_scrolled": ["開包沙漏", "挑戰沙漏"],
    "holdings_flash_sand": ["閃亮沙子"],
    "holdings_pack_hourglass": ["開包沙漏"],
    # 交换页面
    "exchange_record_tab": ["紀錄"],
    "exchange_choose_friend_title": ["請選擇朋友"],
    "exchange_select_card_title": ["請選擇要送給對方的卡牌"],
    "exchange_target_confirm_page": ["編輯卡牌"],
    "exchange_confirm_send_popup": ["確定要送給對方這張卡牌嗎"],
    "exchange_confirm_last_card_popup": ["將交換僅剩的1張卡牌"],
    "exchange_proposed_done_popup": [
        "已將卡牌提議給對方",
        "處於提議階段的卡牌不會在",
    ],
    "exchange_waiting_page": ["正在等待對方回應"],
    "exchange_receive_confirm_page": ["要和這張卡牌交換嗎"],
    "exchange_receive_start_popup": ["要確定並開始交換"],
    "exchange_swipe_to_send": ["向上輕滑卡牌"],
    "exchange_cancel_confirm_popup": [
        "要取消並結束交換嗎",
        "要拒絕並結束交換嗎",
    ],
    "exchange_canceled_done_popup": ["交換已取消"],
    "exchange_send_button": ["交換"],
    "exchange_in_progress": ["交換中"],
    "exchange_confirm_button": ["確認"],
    "exchange_reject_button": ["拒絕"],
    "exchange_cancel_button": ["取消交換"],
    "exchange_insufficient_points": ["閃亮沙子不足"],
    # 交换未解锁弹窗
    "exchange_locked_popup": ["開放條件", "距離開放還剩"],
    # 通用页面
    "popup_ok": ["OK", "ОК"],  # 支持英文OK和俄文ОК（西里尔字母）
    "text_cancel": ["取消"],
    "text_x": ["x"],
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
    "_scene_restart_game": ["Sign in"],
    # ============================================================
    # 对战任务相关（全部以 battle_ 开头）
    # ============================================================
    # 战败提示弹窗
    "battle_defeat_popup": ["前往任務"],
    # 继续对战确认
    "battle_continue_confirm": ["是", "要繼續上次中斷的對戰嗎？"],
    # 经验值结算页面
    "battle_exp_result": ["玩家經驗值"],
    # 对战记录页面
    "battle_record_page": ["對戰紀錄"],
    # 对战中
    "battle_in_progress": [
        "請將基礎寶可夢放置於戰鬥場",
        "你是先攻",
        "你是後攻",
        "對戰對手",
    ],
    # 对战准备页面（牌组详情）
    "battle_prepare": ["對戰！", "首次過關報酬"],
    # 卡组列表页面
    "battle_deck_list": ["擴充組"],
    # 卡组列表页面的"擴充組"按钮（用于点击切换卡包）
    "battle_expansion_button": ["擴充組"],
    # 系列选择页面（扩充组选择）
    "battle_expansion_select": ["選擇擴充組"],
    # 难度选择页面
    "battle_level_select": ["分級對戰"],
    # 难度选择页面的等级完成标记（COMPLETE）
    "battle_level_complete": ["COMPLETE"],
    # 教程完成提示
    "battle_tutorial_complete_hint": ["若想知道更詳細的規則"],
    # 教程列表页面
    "battle_tutorial_list": ["玩法"],
    # 主对战菜单
    "battle_main_menu": ["與他人對戰"],
    # 单人对战按钮
    "battle_solo_button": ["單人對戰"],
    # 误入开包页面
    "battle_show_pack": ["提供比例", "其他擴充包"],
    # 对战模式选择页面（分级对战 + 随机对战）
    "battle_mode_select": ["分級對戰", "隨機對戰"],
    ## 游戏外
    "main_page": ["Pokémon Trad"],
    "close_app_popup": ["关闭应用", "应用信息"],
    "_to_home": ["首页", "重新加载"],
    "text_home": ["首页"],
    # 通用按钮
    "continue": ["繼續", "继续", "Continue"],
    "back_button": ["返回", "返回上一頁", "返回上一页", "Back"],
    "close_button": ["×"],
    "long_press": ["長按", "長按以跳過", "長按開封"],
    # ============================================================
    # 任务奖励领取相关
    # ============================================================
    # 任务奖励页面识别：通过 Tab 栏识别（每日/圖鑑/牌組/掉落）
    # Tab 名称（用于点击切换）
    "rewards_tab_daily": ["每日"],
    "rewards_tab_collection": ["圖鑑"],
    "rewards_tab_deck": ["牌組"],
    "rewards_tab_drop": ["掉落"],
    "rewards_tab_account_link": ["帳號連結"],
    "rewards_tab_premium": ["特級"],
    "rewards_tab_elite_deck": ["精英牌組"],
    "rewards_tab_convenient_cards": ["便利卡牌"],
    "rewards_tab_community_week": ["社群週"],
    "rewards_tab_reward_week": ["獎勵週"],
    "rewards_tab_medal": ["勳章"],
    "rewards_page_exclude": ["收藏板"],
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
    # 每日送卡相关
    # ============================================================
    "gift_tab_send": ["分送"],
    "gift_page_main": ["紀錄", "分送"],
    "gift_choose_friend_title": ["請選擇朋友"],
    "gift_choose_friend_empty": ["沒有朋友"],
    "gift_select_card_title": ["請選擇要分送的卡牌"],
    "gift_filter_modal_title": ["我的最愛", "清除", "OK"],
    "gift_filter_clear": ["清除"],
    "gift_target_page": ["要分送的對象"],
    "gift_hold_count": ["持有張數"],
    "gift_send_button": ["分送"],
    "gift_confirm_send_popup": ["確定要送給對方這張卡牌嗎"],
    "gift_confirm_last_card_popup": ["將分送僅剩的1張卡牌", "確定要繼續嗎"],
    "gift_swipe_to_send": ["向上輕滑卡牌"],
    "gift_search_keyword_marowak": ["嘎啦嘎啦", "嘎啦嘎啦ex"],
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
    "card_challenge_get_exclude": ["升級"],
    "card_challenge_remaining_plays": ["剩餘遊玩次數"],
    "card_challenge_recover": ["恢復"],
    "card_challenge_end_already": ["已挑戰"],
    "card_challenge_end_finished": ["已結束"],
    # ============================================================
    # 新账号初始化流程
    # ============================================================
    "init_select_country": ["選擇國家", "請選擇您居住的國家"],
    "init_country_btn": ["國家/地區"],  # 国家/地区选择按钮
    "init_country_list_close": ["×", "X", "x"],  # 国家列表弹层关闭按钮
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
    "init_open_pack": ["開封"],
    "init_enjoy": ["請好好享受", "隨意遊玩"],
    "init_tap_to_flip": ["點擊來翻開卡牌吧"],
    "init_select_favorite_card": ["選1張喜歡的卡牌吧"],
    # ============================================================
    # 好友关系管理相关
    # ============================================================
    "friend_list": ["朋友", "申請中", "需回覆"],
    "accept": ["接受"],
    "friend_page_list": ["朋友數", "朋友", "申請中", "需回覆"],
    "friend_add_modal": ["新增朋友", "朋友ID搜尋"],
    "friend_page_search_result": ["搜尋結果"],
    "friend_tab_friends": ["朋友"],
    "friend_id_search": ["朋友ID搜尋"],
    "friend_cancel_request": ["取消交友邀請"],
    "friend_apply_button": ["申請"],
    "friend_remove_confirm_title": ["要移除朋友嗎？"],
}
