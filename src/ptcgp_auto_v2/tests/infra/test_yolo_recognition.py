# -*- coding: utf-8 -*-
import logging

import numpy as np
import pytest
from PIL import Image

from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard, YoloCardRecognizer
from ptcgp_auto_v2.tests.fake_adb import FakeAdb
from ptcgp_auto_v2.utils.perceptual_hash import (
    calculate_perceptual_hash,
    calculate_similarity,
    decode_hash_from_base64,
    encode_hash_to_base64,
    pil_to_color_pixels,
)


def _create_solid_image(path, color):
    image = Image.fromarray(np.full((96, 96, 3), color, dtype=np.uint8))
    image.save(path)


def test_perceptual_hash_roundtrip_similarity():
    """感知哈希编码解码后相似度应为1"""
    image = Image.fromarray(np.zeros((96, 96, 3), dtype=np.uint8))
    hash_arr = calculate_perceptual_hash(pil_to_color_pixels(image))
    encoded = encode_hash_to_base64(hash_arr)
    decoded = decode_hash_from_base64(encoded)

    similarity = calculate_similarity(hash_arr, decoded)
    assert similarity == pytest.approx(1.0)


def test_card_hash_manager_ensure_series_ready_loads_hash(tmp_path):
    """Hash 管理器应能下载并加载系列哈希"""

    class FakeCard:
        def __init__(self, card_id, number):
            self.id = card_id
            self.number = number
            self.perceptual_hash = None

    class FakeRepo:
        def __init__(self, cards):
            self._cards = cards

        def get_cards_without_hash(self, set_code):
            return [card for card in self._cards if card.perceptual_hash is None]

        def update_card_hash(self, card_id, hash_value):
            for card in self._cards:
                if card.id == card_id:
                    card.perceptual_hash = hash_value
                    return True
            return False

        def get_cards_with_hash_by_set(self, set_code):
            return {
                card.number: card.perceptual_hash
                for card in self._cards
                if card.perceptual_hash is not None
            }

    class FakeDownloader:
        def __init__(self, base_dir, paths):
            self._paths = paths

        def download_cards_batch(self, set_code, card_numbers):
            return {num: self._paths[num] for num in card_numbers}

    card1 = FakeCard(1, 1)
    card2 = FakeCard(2, 2)
    cards = [card1, card2]

    card1_path = tmp_path / "001.png"
    card2_path = tmp_path / "002.png"
    _create_solid_image(card1_path, 0)
    _create_solid_image(card2_path, 255)

    downloader = FakeDownloader(tmp_path, {1: card1_path, 2: card2_path})
    repo = FakeRepo(cards)

    manager = CardHashManager()
    manager._repo = repo
    manager._downloader = downloader

    assert manager.ensure_series_ready("A1") is True
    assert "A1" in manager.get_loaded_sets()

    image = Image.open(card1_path)
    card_hash = calculate_perceptual_hash(pil_to_color_pixels(image))
    match = manager.find_best_match(card_hash, set_code="A1", threshold=0.9)

    assert match is not None
    assert match[0] == 1


def test_yolo_card_recognizer_scan_pack_result_sorts_by_row():
    """识别结果应按阅读顺序排序"""

    class FakeObb:
        def __init__(self, conf, xyxy):
            self.conf = np.array([conf], dtype=np.float32)
            self.xyxy = np.array([xyxy], dtype=np.float32)

    class FakeResult:
        def __init__(self, obb_list):
            self.obb = obb_list

    class FakeModel:
        def __call__(self, img, verbose=False):
            return [
                FakeResult(
                    [
                        FakeObb(0.99, [60, 80, 90, 110]),
                        FakeObb(0.98, [10, 10, 40, 40]),
                    ]
                )
            ]

    class FakeModelManager:
        def is_model_ready(self):
            return True

        def get_model(self):
            return FakeModel()

    class FakeHashManager:
        def __init__(self):
            self._matches = [(101, 0.95), (102, 0.94)]

        def ensure_series_ready(self, set_code, exclude_promo=False):
            return True

        def find_topk_candidates(
            self, target_hash, set_code=None, topk=10, exclude_promo=False
        ):
            card_number, score = self._matches.pop(0)
            return [(set_code or "A1", card_number, score, np.zeros(8, dtype=np.float32))]

    screenshot = Image.fromarray(np.zeros((120, 120, 3), dtype=np.uint8))
    recognizer = YoloCardRecognizer(
        adb=FakeAdb(screenshot_image=screenshot),
        model_manager=FakeModelManager(),
        hash_manager=FakeHashManager(),
    )

    results = recognizer.scan_pack_result("A1")
    assert [card.card_number for card in results] == [102, 101]


def test_yolo_card_recognizer_scan_info_only_logs_summary(caplog):
    """INFO 级别下只输出汇总日志，不输出逐卡明细。"""

    class FakeRecognizer(YoloCardRecognizer):
        def __init__(self):
            return None

        def _scan_common(
            self,
            set_code,
            obb_threshold,
            similarity_threshold,
            resolve_name=None,
            exclude_promo=False,
        ):
            return (
                [DetectedCard("A1", 1, 0.9, 0.91, (0, 0, 10, 10), (1.0, 2.0))],
                1,
                [],
            )

    resolved = []

    def resolver(set_code, card_number):
        resolved.append((set_code, card_number))
        return f"{set_code}-{card_number}-name"

    recognizer = FakeRecognizer()
    with caplog.at_level(
        logging.INFO, logger="ptcgp_auto_v2.infra.yolo_card_recognizer"
    ):
        results = recognizer.scan(resolve_name=resolver)

    assert [card.card_number for card in results] == [1]
    assert "识别完成: 1/1 张卡牌匹配成功" in caplog.text
    assert "识别明细" not in caplog.text
    assert "第一阶段通过" not in caplog.text
    assert resolved == []


def test_yolo_card_recognizer_scan_debug_logs_details_and_calls_name_resolver(caplog):
    """DEBUG 级别下输出逐卡明细，并按需解析卡名。"""

    class FakeRecognizer(YoloCardRecognizer):
        def __init__(self):
            return None

        def _scan_common(
            self,
            set_code,
            obb_threshold,
            similarity_threshold,
            resolve_name=None,
            exclude_promo=False,
        ):
            return (
                [
                    DetectedCard(
                        "B2",
                        28,
                        0.9,
                        0.93,
                        (0, 0, 10, 10),
                        (1.0, 2.0),
                        match_stage="第一阶段通过",
                        match_note="sim=0.9300",
                    )
                ],
                1,
                [
                    DetectedCard(
                        "B2",
                        99,
                        0.8,
                        0.62,
                        (10, 10, 20, 20),
                        (3.0, 4.0),
                        match_stage="差距不足",
                        match_note="gap=0.0100 < 0.03",
                    )
                ],
            )

    resolved = []

    def resolver(set_code, card_number):
        resolved.append((set_code, card_number))
        return f"{set_code}-{card_number}-name"

    recognizer = FakeRecognizer()
    with caplog.at_level(
        logging.DEBUG, logger="ptcgp_auto_v2.infra.yolo_card_recognizer"
    ):
        recognizer.scan(resolve_name=resolver)

    assert "识别完成: 1/1 张卡牌匹配成功" in caplog.text
    assert "识别明细: 已匹配=1, 未匹配=1" in caplog.text
    assert "阶段=第一阶段通过 sim=0.9300" in caplog.text
    assert "原因=差距不足 gap=0.0100 < 0.03" in caplog.text
    assert "B2-28-name" in caplog.text
    assert "B2-99-name" in caplog.text
    assert resolved == [("B2", 28), ("B2", 99)]
