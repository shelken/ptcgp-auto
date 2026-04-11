# -*- coding: utf-8 -*-
"""fetch_account_info 实机 E2E 场景定义测试。

这个文件只校验新场景的加载约定。
之前缺少 fetch_account_info 的实机场景定义。现在补一条 device-only 场景并锁定其配置。
"""

from __future__ import annotations

import pytest

from ptcgp_auto_v2.tests.e2e.scenario_loader import (
    E2EScenarioConfig,
    list_e2e_scenarios,
    load_e2e_scenario,
)


@pytest.mark.e2e_core
def test_fetch_account_info_device_scenario_is_registered():
    """fetch_account_info 场景应被 device profile 发现。"""
    assert "fetch_account_info_completion" in list_e2e_scenarios("device")


@pytest.mark.e2e_core
def test_fetch_account_info_device_scenario_is_device_only():
    """fetch_account_info 场景只提供 device profile。"""
    config, module = load_e2e_scenario("fetch_account_info_completion", "device")

    assert isinstance(config, E2EScenarioConfig)
    assert config.case_id == "fetch_account_info_completion"
    assert config.profile == "device"
    assert config.task_type == "fetch_account_info"
    assert callable(getattr(module, "run"))

    with pytest.raises(RuntimeError, match="scenario CONFIGS missing profile=core"):
        load_e2e_scenario("fetch_account_info_completion", "core")
