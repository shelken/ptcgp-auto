# -*- coding: utf-8 -*-
"""E2E 场景加载与覆盖规则测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ptcgp_auto_v2.tests.e2e import scenario_loader
from ptcgp_auto_v2.tests.e2e.scenario_loader import (
    E2EScenarioConfig,
    list_e2e_scenarios,
    load_e2e_scenario,
    resolve_e2e_scenario_config,
    validate_e2e_env,
)


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prepare_temp_scenarios(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    package_name: str,
) -> Path:
    package_dir = tmp_path / package_name
    _write(package_dir / "__init__.py", "")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(scenario_loader, "SCENARIOS_PACKAGE", package_name)
    monkeypatch.setattr(scenario_loader, "SCENARIOS_DIR", package_dir)
    return package_dir


def _write_temp_case(
    package_dir: Path,
    case_id: str,
    *,
    include_core: bool = True,
    include_device: bool = False,
):
    case_dir = package_dir / case_id
    _write(case_dir / "__init__.py", "")
    profile_lines: list[str] = []
    if include_core:
        profile_lines.extend(
            [
                '    "core": E2EScenarioConfig(',
                f'        case_id="{case_id}",',
                '        profile="core",',
                f'        description="{case_id} core",',
                '        task_type="claim_gifts",',
                "        params={",
                '            "lease_timeout_seconds": 3,',
                "        },",
                "    ),",
            ]
        )
    if include_device:
        profile_lines.extend(
            [
                '    "device": E2EScenarioConfig(',
                f'        case_id="{case_id}",',
                '        profile="device",',
                f'        description="{case_id} device",',
                '        task_type="claim_gifts",',
                "        params={",
                '            "lease_timeout_seconds": 8,',
                "        },",
                "    ),",
            ]
        )
    _write(
        case_dir / "config.py",
        "\n".join(
            [
                "from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig",
                "",
                "CONFIGS = {",
                *profile_lines,
                "}",
                "",
            ]
        ),
    )
    if include_core:
        _write(case_dir / "core.py", "def run(ctx):\n    return ctx.config.case_id\n")
    if include_device:
        _write(case_dir / "device.py", "def run(ctx):\n    return ctx.config.case_id\n")


@pytest.mark.e2e_core
def test_loader_dynamic_scenario_loads_successfully(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_dynamic_load")
    _write_temp_case(package_dir, "sample_case", include_core=True)

    config, module = load_e2e_scenario("sample_case", "core")

    assert isinstance(config, E2EScenarioConfig)
    assert config.case_id == "sample_case"
    assert callable(getattr(module, "run"))


@pytest.mark.e2e_core
def test_loader_lists_device_case_from_temp_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_list_cases")
    _write_temp_case(package_dir, "device_case", include_core=False, include_device=True)

    assert "device_case" in list_e2e_scenarios("device")


@pytest.mark.e2e_core
def test_override_applies_to_selected_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_override_case")
    _write_temp_case(package_dir, "override_case", include_core=True)

    config = resolve_e2e_scenario_config(
        "override_case",
        "core",
        {
            "PTCGP_E2E_CASE": "override_case",
            "PTCGP_E2E_OVERRIDE_TASK_TYPE": "claim_gifts",
            "PTCGP_E2E_OVERRIDE_ALLOW_SKIPPED": "true",
            "PTCGP_E2E_OVERRIDE_PARAMS__LEASE_TIMEOUT_SECONDS": "9",
        },
    )
    assert config.case_id == "override_case"
    assert config.task_type == "claim_gifts"
    assert config.allow_skipped is True
    assert config.params["lease_timeout_seconds"] == 9


@pytest.mark.e2e_core
def test_override_requires_selected_case():
    with pytest.raises(RuntimeError, match="PTCGP_E2E_CASE is required"):
        validate_e2e_env({"PTCGP_E2E_OVERRIDE_TASK_TYPE": "claim_gifts"})


@pytest.mark.e2e_core
def test_override_rejects_unknown_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_override_field")
    _write_temp_case(package_dir, "normal_case", include_core=True)

    with pytest.raises(RuntimeError, match="unknown scenario override"):
        resolve_e2e_scenario_config(
            "normal_case",
            "core",
            {
                "PTCGP_E2E_CASE": "normal_case",
                "PTCGP_E2E_OVERRIDE_WHATEVER": "x",
            },
        )


@pytest.mark.e2e_core
def test_override_rejects_unknown_param(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_override_param")
    _write_temp_case(package_dir, "normal_case", include_core=True)

    with pytest.raises(RuntimeError, match="unknown scenario param override"):
        resolve_e2e_scenario_config(
            "normal_case",
            "core",
            {
                "PTCGP_E2E_CASE": "normal_case",
                "PTCGP_E2E_OVERRIDE_PARAMS__WHATEVER": "x",
            },
        )


@pytest.mark.e2e_core
def test_missing_config_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_missing_config")
    _write(package_dir / "broken_case" / "__init__.py", "")
    _write(package_dir / "broken_case" / "config.py", "BROKEN = 1\n")
    _write(package_dir / "broken_case" / "core.py", "def run(ctx):\n    return None\n")

    with pytest.raises(RuntimeError, match="scenario config missing CONFIG/CONFIGS"):
        load_e2e_scenario("broken_case", "core")


@pytest.mark.e2e_core
def test_missing_run_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    package_dir = _prepare_temp_scenarios(tmp_path, monkeypatch, "tmp_e2e_missing_run")
    _write(package_dir / "broken_case" / "__init__.py", "")
    _write(
        package_dir / "broken_case" / "config.py",
        "\n".join(
            [
                "from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig",
                "",
                "CONFIG = E2EScenarioConfig(",
                '    case_id="broken_case",',
                '    profile="core",',
                '    description="broken",',
                '    task_type="claim_gifts",',
                "    params={}",
                ")",
            ]
        )
        + "\n",
    )
    _write(package_dir / "broken_case" / "core.py", "BROKEN = 1\n")

    with pytest.raises(RuntimeError, match="scenario module missing run"):
        load_e2e_scenario("broken_case", "core")
