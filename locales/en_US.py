"""
English language configuration
TODO: Fill in actual English text from the game UI
"""

# Battle levels (traverse order, customize as needed)
# Default from Elite to Beginner, to challenge higher difficulty first
BATTLE_LEVELS = ["Elite", "Advanced", "Intermediate", "Beginner"]

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
    # Battle defeat popup - click cancel
    "battle_defeat_popup": {
        "identifiers": ["Go to Missions"],
        "action": "click_cancel",
        "priority": 2,
    },
    # Battle result page - tap to continue
    "battle_result_continue": {
        "identifiers": ["Tap to continue", "TAP TO CONTINUE"],
        "action": "click_identifier",
        "priority": 10,
    },
    # Continue button
    "continue_button": {
        "identifiers": ["Continue"],
        "action": "click_identifier",
        "priority": 11,
    },
    # Battle record page
    "battle_record": {
        "identifiers": ["Battle Record"],
        "action": "click_continue",
        "priority": 15,
    },
    # EXP result page
    "exp_result": {
        "identifiers": ["Player EXP", "EXP"],
        "action": "click_continue",
        "priority": 16,
    },
    # Battle in progress - wait
    "battle_in_progress": {
        "identifiers": [
            "Place a Basic Pokémon",
            "You go first",
            "You go second",
            "Opponent",
        ],
        "action": "wait",
        "priority": 20,
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
        "identifiers": ["Expansion"],
        "templates": ["shalou"],
        "action": "handle_deck_list",
        "priority": 45,
        "exclude_identifiers": ["Select Expansion"],
    },
    # Ranked battle select page (level selection)
    "ranked_battle_select": {
        "identifiers": ["Ranked Battle"],
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

# Multi-language text mapping (for recognizing UI elements)
TEXT_VARIANTS = {
    "continue": [
        "Tap to continue",
        "TAP TO CONTINUE",
        "Continue",
        "CONTINUE",
    ],
    "battle": [
        "Battle!",
        "Battle",
        "BATTLE",
    ],
    "solo_battle": [
        "Solo Battle",
        "SOLO BATTLE",
    ],
    "ranked_battle": [
        "Ranked Battle",
        "RANKED BATTLE",
    ],
    "elite_battle": [
        "Elite Battle",
        "ELITE BATTLE",
    ],
    "expansion": [
        "Expansion",
        "EXPANSION",
    ],
    "complete": [
        "Complete",
        "COMPLETE",
    ],
    "clear": [
        "CLEAR",
        "Clear",
    ],
    "auto": [
        "Auto",
        "AUTO",
    ],
    "cancel": [
        "Cancel",
        "CANCEL",
    ],
    "expansion_button": [
        "Expansion",
        "EXPANSION",
    ],
    "series_a": [
        "Series A",
    ],
    "series_b": [
        "Series B",
    ],
    "select_expansion": [
        "Select Expansion",
    ],
    "series": [
        "Series",
    ],
}
