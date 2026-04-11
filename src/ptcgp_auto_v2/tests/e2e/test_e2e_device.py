# -*- coding: utf-8 -*-
"""通用 device E2E 入口。"""

from __future__ import annotations

import pytest

from ptcgp_auto_v2.tests.e2e.scenario_loader import (
    ScenarioContext,
    e2e_scenario_payload,
    execute_e2e_scenario,
    list_e2e_scenarios,
    load_e2e_scenario,
    resolve_e2e_scenario_config,
)


@pytest.mark.e2e_device
@pytest.mark.parametrize("case_id", list_e2e_scenarios("device"))
def test_e2e_device_case(
    case_id: str,
    device_harness,
    monkeypatch: pytest.MonkeyPatch,
    e2e_runtime_env: dict[str, str],
):
    _, scenario_module = load_e2e_scenario(case_id, "device")
    resolved_config = resolve_e2e_scenario_config(case_id, "device", e2e_runtime_env)
    print(f"[e2e-case] {e2e_scenario_payload(resolved_config)}")
    harness, device_config = device_harness
    ctx = ScenarioContext(
        harness=harness,
        config=resolved_config,
        device_config=device_config,
        monkeypatch=monkeypatch,
    )
    execute_e2e_scenario(ctx, scenario_module)
