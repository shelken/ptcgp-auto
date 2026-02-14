"""好友列表与卡牌扫描流程辅助函数测试。"""

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "ptcgp_auto_v2"
    / "tasks"
    / "utils"
    / "friend_card_flow.py"
)


def _load_module():
    """直接按文件加载模块，避免引入任务包的重依赖。"""
    spec = importlib.util.spec_from_file_location(
        "friend_card_flow_for_test", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_find_target_search_plus_box_ignores_confusing_chars_in_nickname():
    """昵称含 I/l/1 易混字符时，仍可命中同一行加号。"""
    module = _load_module()
    ocr_results = [
        {"text": "lllkk99", "box": [380, 290, 500, 335]},
        {"text": "Lv. 6", "box": [350, 245, 450, 280]},
    ]
    plus_boxes = [
        (780, 280, 840, 340),
    ]

    result = module.find_target_search_plus_box(
        ocr_results=ocr_results,
        target_nickname="Illkk99",
        search_plus_boxes=plus_boxes,
        row_threshold_y=130,
    )

    assert result == plus_boxes[0]


def test_find_target_search_plus_box_matches_after_threshold_relaxed():
    """阈值从 130 放宽后，133 像素偏差可命中同一行。"""
    module = _load_module()
    ocr_results = [
        {"text": "lllkk99", "box": [380, 290, 500, 335]},
    ]
    plus_boxes = [
        (780, 430, 840, 462),  # 与昵称中心 y 差约 133，略高于 130
        (780, 640, 840, 672),
    ]

    result = module.find_target_search_plus_box(
        ocr_results=ocr_results,
        target_nickname="Illkk99",
        search_plus_boxes=plus_boxes,
        row_threshold_y=150,
    )

    assert result == plus_boxes[0]


def test_find_target_search_plus_box_not_require_plus_on_right_side():
    """加号模板坐标偏左时，仍按同一行Y轴匹配。"""
    module = _load_module()
    ocr_results = [
        {"text": "lllkk99", "box": [380, 290, 500, 335]},
    ]
    plus_boxes = [
        (300, 298, 360, 340),
    ]

    result = module.find_target_search_plus_box(
        ocr_results=ocr_results,
        target_nickname="Illkk99",
        search_plus_boxes=plus_boxes,
        row_threshold_y=150,
    )

    assert result == plus_boxes[0]
