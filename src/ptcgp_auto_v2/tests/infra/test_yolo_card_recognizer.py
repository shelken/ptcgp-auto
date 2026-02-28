# -*- coding: utf-8 -*-
"""
YoloCardRecognizer 测试

验证 exclude_promo 参数行为：
- exclude_promo=True 时排除 PROMO 系列
- 普通系列缺失 Hash 仍可下载
"""

import pytest
from unittest.mock import Mock, patch


class TestExcludePromo:
    """exclude_promo 参数测试"""

    def test_scan_passes_exclude_promo_to_hash_manager(self):
        """测试 scan 方法传递 exclude_promo 给 hash_manager"""
        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
            },
        ):
            from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer

            mock_adb = Mock()
            mock_model_manager = Mock()
            mock_hash_manager = Mock()

            recognizer = YoloCardRecognizer(
                adb=mock_adb,
                model_manager=mock_model_manager,
                hash_manager=mock_hash_manager,
            )

            # Mock 模型就绪
            mock_model_manager.is_model_ready.return_value = True
            mock_adb.screenshot.return_value = Mock()
            mock_model_manager.get_model.return_value = Mock()
            mock_model_manager.get_model.return_value.return_value = [Mock()]

            # 调用 scan 并传入 exclude_promo=True
            with patch.object(recognizer, "_detect_cards", return_value=[]):
                recognizer.scan(set_code="A1", exclude_promo=True)

            # 验证 hash_manager.ensure_series_ready 被调用且传入了 exclude_promo
            mock_hash_manager.ensure_series_ready.assert_called_once()
            call_kwargs = mock_hash_manager.ensure_series_ready.call_args
            assert call_kwargs.kwargs.get("exclude_promo")

    def test_global_scan_excludes_promo_series(self):
        """测试全局扫描时排除 PROMO 系列"""
        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
            },
        ):
            from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer

            mock_adb = Mock()
            mock_model_manager = Mock()
            mock_hash_manager = Mock()

            recognizer = YoloCardRecognizer(
                adb=mock_adb,
                model_manager=mock_model_manager,
                hash_manager=mock_hash_manager,
            )

            mock_model_manager.is_model_ready.return_value = True
            mock_adb.screenshot.return_value = Mock()

            # 调用全局扫描并排除 PROMO
            with patch.object(recognizer, "_detect_cards", return_value=[]):
                recognizer.scan(set_code=None, exclude_promo=True)

            # 验证 load_all_hashes 被调用且传入了 exclude_promo
            mock_hash_manager.load_all_hashes.assert_called_once()
            call_kwargs = mock_hash_manager.load_all_hashes.call_args
            assert call_kwargs.kwargs.get("exclude_promo")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
