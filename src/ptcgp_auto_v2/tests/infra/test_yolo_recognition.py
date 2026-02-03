# -*- coding: utf-8 -*-
import numpy as np
import pytest
from PIL import Image

from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
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

        def ensure_series_ready(self, set_code):
            return True

        def find_best_match(self, target_hash, set_code=None, threshold=0.8):
            return self._matches.pop(0)

    class FakeAdb:
        def screenshot(self):
            return Image.fromarray(np.zeros((120, 120, 3), dtype=np.uint8))

        def scaled_x(self, value):
            return value

        def scaled_y(self, value):
            return value

    recognizer = YoloCardRecognizer(
        adb=FakeAdb(),
        model_manager=FakeModelManager(),
        hash_manager=FakeHashManager(),
    )

    results = recognizer.scan_pack_result("A1")
    assert [card.card_number for card in results] == [102, 101]
