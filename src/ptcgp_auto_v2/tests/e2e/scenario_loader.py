# -*- coding: utf-8 -*-
"""E2E 场景发现、加载与覆盖解析。"""

from __future__ import annotations

import importlib
from collections.abc import Mapping as MappingABC
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Mapping, Optional

if TYPE_CHECKING:
    from ptcgp_auto_v2.tests.e2e.harness import SchedulerHarness

E2E_CASE_ENV = "PTCGP_E2E_CASE"
E2E_OVERRIDE_PREFIX = "PTCGP_E2E_OVERRIDE_"
SCENARIOS_PACKAGE = "ptcgp_auto_v2.tests.e2e.scenarios"
SCENARIOS_DIR = Path(__file__).with_name("scenarios")
TOP_LEVEL_OVERRIDE_FIELDS = {"description", "task_type", "allow_skipped"}
PROFILE_MODULE_NAMES = {"core", "device"}


@dataclass(frozen=True)
class E2EScenarioConfig:
    """E2E 场景元信息。"""

    case_id: str
    profile: str
    description: str
    task_type: str
    allow_skipped: bool = False
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceRuntimeConfig:
    """实机 E2E 运行时配置。"""

    device_address: str
    account_id: int
    worker_mode: str


@dataclass
class ScenarioContext:
    """场景执行上下文。"""

    harness: "SchedulerHarness"
    config: E2EScenarioConfig
    monkeypatch: Any
    device_config: Optional[DeviceRuntimeConfig] = None

    def log(self, message: str):
        print(f"[e2e-scenario] {self.config.case_id}: {message}")

    def require_device_config(self) -> DeviceRuntimeConfig:
        if self.device_config is None:
            raise RuntimeError(f"device config required: {self.config.case_id}")
        return self.device_config


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean override: {value}")


def _cast_like(current_value: Any, raw_value: str):
    if isinstance(current_value, bool):
        return _parse_bool(raw_value)
    if isinstance(current_value, int):
        return int(raw_value)
    if isinstance(current_value, float):
        return float(raw_value)
    return raw_value


def _scenario_dir_names() -> list[str]:
    names: list[str] = []
    for child in sorted(SCENARIOS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name == "__pycache__":
            continue
        if not (child / "config.py").exists():
            continue
        names.append(child.name)
    return names


def _load_config_module(case_id: str) -> ModuleType:
    return importlib.import_module(f"{SCENARIOS_PACKAGE}.{case_id}.config")


def _resolve_profile_config(case_id: str, profile: str) -> E2EScenarioConfig:
    config_module = _load_config_module(case_id)
    configs = getattr(config_module, "CONFIGS", None)
    if isinstance(configs, MappingABC):
        config = configs.get(profile)
        if not isinstance(config, E2EScenarioConfig):
            raise RuntimeError(f"scenario CONFIGS missing profile={profile}: {case_id}")
        return config
    config = getattr(config_module, "CONFIG", None)
    if not isinstance(config, E2EScenarioConfig):
        raise RuntimeError(f"scenario config missing CONFIG/CONFIGS: {case_id}")
    if config.profile != profile:
        raise RuntimeError(
            f"scenario profile mismatch: expected {profile}, got {config.profile}"
        )
    return config


def _load_scenario_module(case_id: str, profile: str) -> ModuleType:
    module_names = [profile, "scenario"]
    last_error: Optional[ModuleNotFoundError] = None
    for module_name in module_names:
        full_module_name = f"{SCENARIOS_PACKAGE}.{case_id}.{module_name}"
        try:
            return importlib.import_module(full_module_name)
        except ModuleNotFoundError as exc:
            if exc.name != full_module_name:
                raise
            last_error = exc
            continue
    raise RuntimeError(f"scenario module not found for profile={profile}: {case_id}") from last_error


def _get_scenario_entry(module: ModuleType):
    entry = getattr(module, "run", None) or getattr(module, "execute", None)
    if not callable(entry):
        raise RuntimeError("scenario module missing run(ctx) or execute(ctx)")
    return entry


def load_e2e_scenario(case_id: str, profile: str) -> tuple[E2EScenarioConfig, ModuleType]:
    """按约定加载场景配置和执行模块。"""
    if case_id not in _scenario_dir_names():
        raise KeyError(f"unknown e2e scenario: {case_id}")

    if profile not in PROFILE_MODULE_NAMES:
        raise RuntimeError(f"invalid scenario profile: {profile}")

    config = _resolve_profile_config(case_id, profile)
    scenario_module = _load_scenario_module(case_id, profile)
    if config.case_id != case_id:
        raise RuntimeError(
            f"scenario CONFIG.case_id mismatch: expected {case_id}, got {config.case_id}"
        )
    if config.profile not in PROFILE_MODULE_NAMES:
        raise RuntimeError(f"invalid scenario profile: {config.profile}")
    if config.profile != profile:
        raise RuntimeError(
            f"scenario CONFIG.profile mismatch: expected {profile}, got {config.profile}"
        )
    _get_scenario_entry(scenario_module)
    return config, scenario_module


def list_e2e_scenarios(profile: str) -> list[str]:
    """列出指定 profile 的全部场景。"""
    if profile not in PROFILE_MODULE_NAMES:
        raise RuntimeError(f"invalid scenario profile: {profile}")
    case_ids: list[str] = []
    for case_id in _scenario_dir_names():
        try:
            load_e2e_scenario(case_id, profile)
            case_ids.append(case_id)
        except RuntimeError:
            continue
    return case_ids


def get_e2e_override_keys(env: Mapping[str, str]) -> list[str]:
    """列出当前环境中的 override 变量。"""
    return sorted(
        key for key in env if key.startswith(E2E_OVERRIDE_PREFIX) and env[key].strip()
    )


def validate_e2e_env(env: Mapping[str, str]):
    """校验环境变量组合是否合法。"""
    override_keys = get_e2e_override_keys(env)
    if override_keys and not env.get(E2E_CASE_ENV, "").strip():
        joined = ", ".join(override_keys)
        raise RuntimeError(f"{E2E_CASE_ENV} is required when using overrides: {joined}")


def resolve_e2e_scenario_config(
    case_id: str,
    profile: str,
    env: Mapping[str, str],
) -> E2EScenarioConfig:
    """读取并应用环境变量覆盖后的场景配置。"""
    validate_e2e_env(env)
    base_config, _ = load_e2e_scenario(case_id, profile)
    top_level_overrides: dict[str, Any] = {}
    param_overrides = dict(base_config.params)

    for env_name in get_e2e_override_keys(env):
        raw_value = env[env_name].strip()
        override_name = env_name[len(E2E_OVERRIDE_PREFIX) :]
        if override_name.startswith("PARAMS__"):
            param_name = override_name[len("PARAMS__") :].lower()
            if param_name not in param_overrides:
                raise RuntimeError(f"unknown scenario param override: {env_name}")
            param_overrides[param_name] = _cast_like(param_overrides[param_name], raw_value)
            continue

        field_name = override_name.lower()
        if field_name not in TOP_LEVEL_OVERRIDE_FIELDS:
            raise RuntimeError(f"unknown scenario override: {env_name}")
        current_value = getattr(base_config, field_name)
        top_level_overrides[field_name] = _cast_like(current_value, raw_value)

    resolved = replace(base_config, params=param_overrides, **top_level_overrides)
    return resolved


def execute_e2e_scenario(ctx: ScenarioContext, module: ModuleType):
    """执行已加载场景模块。"""
    entry = _get_scenario_entry(module)
    entry(ctx)


def e2e_scenario_payload(config: E2EScenarioConfig) -> dict[str, object]:
    """序列化场景配置用于日志输出。"""
    return asdict(config)
