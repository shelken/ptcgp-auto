# -*- coding: utf-8 -*-
"""HRW 分配模拟脚本测试（复用正式逻辑）。"""

from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import SimpleNamespace


def _load_script_module():
    """动态加载 scripts 下的模拟脚本模块。"""
    script_path = (
        Path(__file__).resolve().parents[4]
        / "scripts"
        / "simulate_hrw_pack_distribution.py"
    )
    spec = spec_from_file_location("simulate_hrw_pack_distribution", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 simulate_hrw_pack_distribution.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_reuses_formal_constants():
    """脚本应直接复用正式常量，避免参数漂移。"""
    module = _load_script_module()
    from ptcgp_auto_v2.config.constants import PACK_AUTO_HRW_PROGRESS_BETA

    assert module.PACK_AUTO_HRW_PROGRESS_BETA == PACK_AUTO_HRW_PROGRESS_BETA


def test_run_simulation_prints_single_seed_from_formal_snapshot():
    """脚本应基于正式快照输出单一 seed 结果。"""
    module = _load_script_module()

    class FakeCardRepo:
        pass

    setattr(module, "CardRepository", FakeCardRepo)
    setattr(
        module,
        "get_hrw_distribution_snapshot",
        lambda **_: {
            "selected_seed": "seed-weekly-001",
            "best_metrics": {"weighted_rmse": 1.23, "std": 2.34, "spread": 5},
            "pack_map": {
                "A1/Pikachu": SimpleNamespace(set_code="A1", name="Pikachu"),
                "A2/Charizard": SimpleNamespace(set_code="A2", name="Charizard"),
            },
            "assignment_map": {
                "id:1": "A1/Pikachu",
                "id:2": "A2/Charizard",
                "id:3": "A2/Charizard",
            },
            "pack_weights": {"A1/Pikachu": 1.0, "A2/Charizard": 2.0},
            "progress_stats": {
                "Pikachu": {"owned_target": 1, "total_target": 2},
                "Charizard": {"owned_target": 0, "total_target": 3},
            },
            "progress_ratio_map": {"A1/Pikachu": 0.5, "A2/Charizard": 0.0},
            "account_count": 3,
            "candidate_count": 2,
        },
    )

    output = StringIO()
    with redirect_stdout(output):
        module.run_simulation()

    text = output.getvalue()
    assert "最终使用seed（单一）" in text
    assert "seed=seed-weekly-001" in text
    assert "A1" in text and "Pikachu" in text
    assert "A2" in text and "Charizard" in text
