"""
English language configuration
TODO: Fill in actual English text from the game UI
"""

# Battle levels (traverse order, customize as needed)
# Default from Elite to Beginner, to challenge higher difficulty first
BATTLE_LEVELS = ["Expert", "Advanced", "Intermediate", "Beginner"]

# Deck keyword (used to extract pack name from title)
# Format: "Carnivine Deck (Triumphant Light)"
DECK_KEYWORD = "Deck"

# Series list (traverse in this order)
SERIES = ["A", "B"]

# Page detection configuration
# Each page definition:
#   - identifiers: Text list to identify the page (any match is sufficient)
#   - action: Action to execute on this page
#   - priority: Priority (lower number = higher priority, used when multiple pages match)
#   - exact_match: Whether to use exact match (default False, uses contains match)

PAGES = {
    # Popup - highest priority (exact match to avoid matching POKéMON)
    "popup_ok": {
        "identifiers": ["OK", "Confirm"],
        "action": "click_identifier",
        "priority": 1,
        "exact_match": True,
    },
    # Network error popup - click retry
    "network_error_popup": {
        "identifiers": ["Retry", "Try Again"],
        "action": "click_identifier",
        "priority": 1,
        "exact_match": True,
    },
    # Battle defeat popup - click cancel
    "battle_defeat_popup": {
        "identifiers": ["To Missions"],
        "action": "click_cancel",
        "priority": 2,
    },
    # Battle result page - tap to continue
    "battle_result_continue": {
        "identifiers": ["Tap to Proceed"],
        "action": "click_identifier",
        "priority": 10,
    },
    # Continue button
    "continue_button": {
        "identifiers": ["Next", "Continue"],
        "action": "click_identifier",
        "priority": 11,
        "exclude_identifiers": ["next turn"],
    },
    # Battle record page
    "battle_record": {
        "identifiers": ["Battle Log"],
        "action": "tap_screen_center",
        "priority": 15,
    },
    # EXP result page
    "exp_result": {
        "identifiers": ["Player EXP"],
        "action": "tap_screen_center",
        "priority": 16,
    },
    # Battle in progress - wait
    "battle_in_progress": {
        "identifiers": [
            "Opponent",
        ],
        "action": "wait_battle",
        "priority": 20,
        "exact_match": True,
        # "exclude_identifiers": ["Knock Out your opponent's Active"],
    },
    # Deck detail page - has battle button
    "deck_detail": {
        "identifiers": ["Battle!"],
        "action": "start_battle",
        "priority": 30,
    },
    # Expansion select page (select which card pack)
    "expansion_select": {
        "identifiers": ["Select Expansion"],
        "action": "handle_expansion_select",
        "priority": 42,
    },
    # Deck list page - in a card pack, has Expansion button
    "deck_list": {
        "identifiers": ["Expansions"],
        "templates": ["shalou"],
        "action": "handle_deck_list",
        "priority": 45,
        "exclude_identifiers": ["Select Expansion"],
    },
    # Ranked battle select page (level selection)
    "ranked_battle_select": {
        "identifiers": ["Step-Up Battle"],
        "action": "select_level",
        "priority": 50,
        "exclude_identifiers": ["Expansion"],
    },
    # Main battle menu - click solo battle
    "battle_menu": {
        "identifiers": ["Versus"],  # 主菜单有 Versus 按钮
        "action": "click_solo_battle",
        "priority": 55,
    },
    # Solo battle main page (shows various missions)
    "solo_battle_main": {
        "identifiers": ["Solo"],
        "action": "find_incomplete",
        "priority": 60,
        "exclude_identifiers": ["Versus"],  # 排除主菜单（同时有 Versus 和 Solo）
    },
}

# Helper text patterns (for actions module queries)
TEXT_PATTERNS = {
    "auto": ["Auto", "AUTO"],
    "series": {
        "A": ["A Series", "Series A"],
        "B": ["B Series", "Series B"],
    },
    "skip_titles": ["Select Expansion", "Series"],
    "no_battles": ["no battles available", "There are no battles"],
    "cancel": ["Cancel"],
    "expansion_button": ["Expansion"],
    "ranked_battle": ["Ranked"],
    "solo_battle": ["Solo"],
}
