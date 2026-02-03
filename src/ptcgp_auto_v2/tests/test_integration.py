# -*- coding: utf-8 -*-
"""
YOLO+Hash 卡牌识别集成测试

测试场景:
1. 模型未加载完成场景
2. Hash 未就绪场景
3. 排序逻辑（按阅读顺序）
4. Hash Manager 系列就绪与匹配流程
"""

from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
from PIL import Image

from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.model_manager import ModelManager
from ptcgp_auto_v2.infra.yolo_card_recognizer import (
    DetectedCard,
    YoloCardRecognizer,
)
from ptcgp_auto_v2.utils.perceptual_hash import encode_hash_to_base64


class TestYoloCardRecognizerIntegration:
    """YoloCardRecognizer 集成测试"""

    @pytest.fixture
    def mock_adb(self):
        adb = Mock()
        adb.screenshot.return_value = Image.new(
            "RGB", (1080, 1920), color=(100, 100, 100)
        )
        adb.scaled_x.side_effect = lambda value: value
        adb.scaled_y.side_effect = lambda value: value
        return adb

    @pytest.fixture
    def mock_model_manager(self):
        manager = Mock(spec=ModelManager)
        manager.is_model_ready.return_value = True
        manager.get_model.return_value = Mock()
        return manager

    @pytest.fixture
    def mock_hash_manager(self):
        manager = Mock(spec=CardHashManager)
        manager.ensure_series_ready.return_value = True
        return manager

    @pytest.fixture
    def recognizer(self, mock_adb, mock_model_manager, mock_hash_manager):
        return YoloCardRecognizer(
            adb=mock_adb,
            model_manager=mock_model_manager,
            hash_manager=mock_hash_manager,
        )

    def test_model_not_ready(self, recognizer, mock_model_manager):
        """模型未加载完成时返回空列表"""
        mock_model_manager.is_model_ready.return_value = False
        assert recognizer.scan_pack_result("A1") == []

    def test_hash_not_ready(self, recognizer, mock_hash_manager):
        """Hash 未就绪时返回空列表"""
        mock_hash_manager.ensure_series_ready.return_value = False
        assert recognizer.scan_pack_result("A1") == []

    def test_sort_by_reading_order(self, recognizer):
        """按阅读顺序排序（从上到下，从左到右）"""
        # 使用行阈值常量，确保第二行与第一行差值大于阈值
        row_gap = YoloCardRecognizer.BASE_ROW_THRESHOLD + 5
        cards = [
            DetectedCard(None, 1, 0.9, 0.8, (0, 0, 100, 100), (500.0, 100.0 + row_gap)),
            DetectedCard(None, 2, 0.9, 0.8, (0, 0, 100, 100), (100.0, 100.0 + row_gap)),
            DetectedCard(None, 3, 0.9, 0.8, (0, 0, 100, 100), (100.0, 100.0)),
            DetectedCard(None, 4, 0.9, 0.8, (0, 0, 100, 100), (500.0, 100.0)),
        ]

        sorted_cards = recognizer._sort_by_reading_order(cards)
        assert [c.card_number for c in sorted_cards] == [3, 4, 2, 1]

    def test_scan_global_without_set_code(
        self, recognizer, mock_hash_manager, mock_adb
    ):
        """scan 在无 set_code 时走全局匹配并返回 set_code 信息"""
        mock_hash_manager.load_all_hashes.return_value = True

        fake_cropped = np.zeros((20, 20, 3), dtype=np.uint8)
        with patch.object(recognizer, "_detect_cards") as mock_detect:
            mock_detect.return_value = [
                {
                    "index": 1,
                    "confidence": 0.99,
                    "cropped": fake_cropped,
                    "bbox": (0, 0, 10, 10),
                    "center": (5.0, 5.0),
                }
            ]

            mock_hash_manager.find_best_match.return_value = ("A1", 12, 0.88)

            results = recognizer.scan(set_code=None)

        assert len(results) == 1
        result = results[0]
        assert result.set_code == "A1"
        assert result.card_number == 12
        assert result.similarity == 0.88


class TestCardHashManagerIntegration:
    """CardHashManager 集成测试"""

    @pytest.fixture
    def hash_manager(self):
        with patch(
            "ptcgp_auto_v2.infra.card_hash_manager.CardRepository"
        ) as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo

            manager = CardHashManager()
            manager._repo = mock_repo
            yield manager, mock_repo

    def test_ensure_series_ready(self, hash_manager):
        """系列就绪流程：下载缺失卡牌并写入 Hash"""
        manager, mock_repo = hash_manager

        mock_card = Mock()
        mock_card.number = 1
        mock_card.id = 101

        test_hash = np.array([0b11110000] * 6, dtype=np.uint32)
        encoded_hash = encode_hash_to_base64(test_hash)

        mock_repo.get_cards_without_hash.return_value = [mock_card]
        mock_repo.get_cards_with_hash_by_set.return_value = {1: encoded_hash}

        with patch.object(manager._downloader, "download_cards_batch") as mock_download:
            with patch.object(manager, "_compute_and_save_hash") as mock_compute:
                mock_download.return_value = {1: Path("/tmp/1.png")}
                mock_compute.return_value = True

                assert manager.ensure_series_ready("A1") is True
                mock_repo.get_cards_without_hash.assert_called_once_with("A1")
                mock_download.assert_called_once_with("A1", [1])
                mock_compute.assert_called_once_with(101, Path("/tmp/1.png"))

    def test_find_best_match(self, hash_manager):
        """系列内匹配流程"""
        manager, mock_repo = hash_manager

        hash1 = encode_hash_to_base64(np.array([0b11111111] * 6, dtype=np.uint32))
        hash2 = encode_hash_to_base64(np.array([0b00000000] * 6, dtype=np.uint32))
        mock_repo.get_cards_with_hash_by_set.return_value = {1: hash1, 2: hash2}

        target_hash = np.array([0b11111111] * 6, dtype=np.uint32)
        result = manager.find_best_match(target_hash, set_code="A1", threshold=0.8)

        assert result is not None
        card_number, similarity = result
        assert card_number == 1
        assert similarity == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
