"""动作工具模块"""
from .scroll import ScrollHelper as ScrollHelper
from .ocr_helpers import (
    find_text_by_variants as find_text_by_variants,
    find_all_by_variants as find_all_by_variants,
    extract_progress as extract_progress,
    find_items_on_same_row as find_items_on_same_row,
    group_by_row as group_by_row,
    find_auto_mode_button as find_auto_mode_button,
)
from .navigation import (
    go_back as go_back,
    close_popup as close_popup,
    detect_and_close_popup as detect_and_close_popup,
)
