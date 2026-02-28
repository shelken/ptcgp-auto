# -*- coding: utf-8 -*-
"""
CardHashManager 测试

验证 exclude_promo 参数行为：
- exclude_promo=True 时跳过 PROMO 系列
- 普通系列仍可正常下载缺失 Hash
"""

import pytest
from unittest.mock import Mock, patch


class TestExcludePromo:
    """exclude_promo 参数测试"""

    def test_ensure_series_ready_skips_promo_when_exclude_true(self):
        """测试 ensure_series_ready 在 exclude_promo=True 时跳过 PROMO"""
        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.utils.perceptual_hash": Mock(),
                "ptcgp_auto_v2.utils.image_manager": Mock(),
            },
        ):
            from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager

            manager = CardHashManager(enable_download=False)
            manager._repo = Mock()

            # 调用 PROMO 系列且 exclude_promo=True
            result = manager.ensure_series_ready("PROMO-A1", exclude_promo=True)

            # 应该直接返回 True，不查询数据库
            assert result is True
            manager._repo.get_cards_without_hash.assert_not_called()

    def test_ensure_series_ready_processes_normal_series(self):
        """测试 ensure_series_ready 处理普通系列"""
        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.utils.perceptual_hash": Mock(),
                "ptcgp_auto_v2.utils.image_manager": Mock(),
            },
        ):
            from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager

            manager = CardHashManager(enable_download=False)
            manager._repo = Mock()
            manager._repo.get_cards_without_hash.return_value = []
            manager._repo.get_cards_with_hash_by_set.return_value = {}

            # 调用普通系列
            result = manager.ensure_series_ready("A1", exclude_promo=True)

            # 应该正常处理
            assert result is True
            manager._repo.get_cards_without_hash.assert_called_once_with("A1")

    def test_load_all_hashes_excludes_promo_series(self):
        """测试 load_all_hashes 排除 PROMO 系列"""
        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.utils.perceptual_hash": Mock(),
                "ptcgp_auto_v2.utils.image_manager": Mock(),
            },
        ):
            from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager

            manager = CardHashManager(enable_download=False)
            manager._repo = Mock()

            # 模拟返回 PROMO 和普通系列
            mock_set_promo = Mock()
            mock_set_promo.code = "PROMO-A1"
            mock_set_normal = Mock()
            mock_set_normal.code = "A1"
            manager._repo.get_all_sets.return_value = [mock_set_promo, mock_set_normal]

            manager._repo.get_cards_without_hash.return_value = []
            manager._repo.get_cards_with_hash_by_set.return_value = {}

            # 加载全局 Hash，排除 PROMO
            result = manager.load_all_hashes(exclude_promo=True)

            # 应该成功
            assert result is True
            # ensure_series_ready 应该只被调用一次（仅普通系列 A1）
            # PROMO-A1 应该被跳过
            manager._repo.get_cards_without_hash.assert_called_once()
            # 验证只查询了普通系列 A1
            assert manager._repo.get_cards_without_hash.call_args[0][0] == "A1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
