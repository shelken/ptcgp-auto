# -*- coding: utf-8 -*-
"""
使用正式识别流程输出检测可视化图

示例：
PYTHONPATH=src python scripts/test_prod_scan_visual.py --adb 127.0.0.1:5775 --out output/prod_detection.jpg
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer


def main() -> None:
    parser = argparse.ArgumentParser(description="正式识别流程可视化输出")
    parser.add_argument("--adb", required=True, help="ADB 设备地址")
    parser.add_argument(
        "--out", default="output/prod_detection.jpg", help="输出图片路径"
    )
    parser.add_argument("--conf", type=float, default=0.55, help="YOLO 置信度阈值")
    args = parser.parse_args()

    adb = AdbController(args.adb)
    if not adb.connect():
        raise RuntimeError(f"无法连接设备: {args.adb}")

    screenshot = adb.screenshot()
    if not screenshot:
        raise RuntimeError("截图失败")

    model_manager = get_model_manager()
    model_manager.load_model_async()
    if not model_manager.wait_for_model(timeout=120):
        raise RuntimeError("模型加载超时")

    recognizer = YoloCardRecognizer(
        adb=adb, model_manager=model_manager, hash_manager=CardHashManager()
    )

    detected = recognizer._detect_cards(screenshot, conf_threshold=args.conf)
    if not detected:
        print("未检测到卡牌")

    img_array = np.array(screenshot)
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    for card in detected:
        x1, y1, x2, y2 = card["bbox"]
        cv2.rectangle(img_bgr, (x1, y1), (x2, y2), (0, 255, 0), 3)
        conf_text = f"{card['confidence']:.2f}"
        text_size = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        text_x = x1
        text_y = y1 - 5 if y1 > 20 else y1 + 20
        cv2.putText(
            img_bgr,
            conf_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), img_bgr)
    print(f"检测到 {len(detected)} 张卡牌，已保存: {out_path}")


if __name__ == "__main__":
    main()
