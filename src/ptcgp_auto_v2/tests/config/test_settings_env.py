# -*- coding: utf-8 -*-
"""settings .env 加载测试。"""

import os

from ptcgp_auto_v2.config import settings as settings_module


def test_load_dotenv_sets_value_when_env_absent(tmp_path, monkeypatch):
    """当环境变量不存在时，应从 .env 加载值。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PTCGP_WEBHOOK_URL=https://example.test/webhook\n")
    monkeypatch.delenv("PTCGP_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(settings_module, "_dotenv_loaded", False)

    settings_module.load_dotenv()

    assert os.environ.get("PTCGP_WEBHOOK_URL") == "https://example.test/webhook"


def test_load_dotenv_does_not_override_existing_env(tmp_path, monkeypatch):
    """当环境变量已存在时，.env 不应覆盖。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "PTCGP_WEBHOOK_URL=https://example.test/from-dotenv\n"
    )
    monkeypatch.setenv("PTCGP_WEBHOOK_URL", "https://example.test/from-env")
    monkeypatch.setattr(settings_module, "_dotenv_loaded", False)

    settings_module.load_dotenv()

    assert os.environ.get("PTCGP_WEBHOOK_URL") == "https://example.test/from-env"


def test_settings_from_env_reads_values_after_loading_dotenv(tmp_path, monkeypatch):
    """from_env 应能读取 .env 中的 v2 配置变量。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PTCGP_WEB_PORT=18080\nPTCGP_DEBUG=true\n")
    monkeypatch.delenv("PTCGP_WEB_PORT", raising=False)
    monkeypatch.delenv("PTCGP_DEBUG", raising=False)
    monkeypatch.setattr(settings_module, "_dotenv_loaded", False)

    settings = settings_module.Settings.from_env()

    assert settings.web_port == 18080
    assert settings.debug is True
    assert settings.log_level == "DEBUG"


def test_set_settings_also_loads_dotenv(tmp_path, monkeypatch):
    """主流程调用 set_settings 时也应先加载 .env。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PTCGP_WEBHOOK_URL=https://example.test/webhook\n")
    monkeypatch.delenv("PTCGP_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(settings_module, "_dotenv_loaded", False)

    settings_module.set_settings(settings_module.Settings())

    assert os.environ.get("PTCGP_WEBHOOK_URL") == "https://example.test/webhook"


def test_apply_webhook_cli_overrides_webhook_url_has_highest_priority(monkeypatch):
    """CLI 的 webhook_url 应覆盖环境变量。"""
    monkeypatch.setenv("PTCGP_WEBHOOK_URL", "https://example.test/from-env")

    settings_module.apply_webhook_cli_overrides(
        webhook_url="https://example.test/from-cli",
        notify_key=None,
    )

    assert os.environ.get("PTCGP_WEBHOOK_URL") == "https://example.test/from-cli"


def test_apply_webhook_cli_overrides_notify_key_overrides_env_url(monkeypatch):
    """仅传 CLI notify_key 时，也应覆盖现有环境 URL。"""
    monkeypatch.setenv("PTCGP_WEBHOOK_URL", "https://example.test/from-env")

    settings_module.apply_webhook_cli_overrides(
        webhook_url=None,
        notify_key="cli-key-123",
    )

    assert (
        os.environ.get("PTCGP_WEBHOOK_URL")
        == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=cli-key-123"
    )
