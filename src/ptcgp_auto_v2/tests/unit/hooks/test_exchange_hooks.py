# -*- coding: utf-8 -*-
"""交换卡牌 Hook 单元测试。"""

from types import SimpleNamespace

from ptcgp_auto_v2.core.hooks import HookContext, HookResult
from ptcgp_auto_v2.hooks.exchange_hooks import ExchangeDelayPostHook


def _context(task: SimpleNamespace) -> HookContext:
    return HookContext(
        device=SimpleNamespace(),
        account=SimpleNamespace(),
        task=task,
        executor=SimpleNamespace(),
    )


def test_exchange_runtime_delay_returns_delay_with_reason():
    task = SimpleNamespace(
        task_type="exchange_cards",
        _ctx=SimpleNamespace(
            runtime=SimpleNamespace(
                delay_seconds=12,
                delay_reason="交换等待中",
            )
        ),
    )

    result, data = ExchangeDelayPostHook().run(_context(task))

    assert result == HookResult.DELAY
    assert data == {"delay_seconds": 12.0, "reason": "交换等待中"}


def test_exchange_old_private_delay_fields_without_runtime_continue():
    task = SimpleNamespace(
        task_type="exchange_cards",
        _delay_seconds=12,
        _delay_reason="旧字段等待",
    )

    result, data = ExchangeDelayPostHook().run(_context(task))

    assert result == HookResult.CONTINUE
    assert data == {}


def test_exchange_runtime_delay_uses_default_reason_when_reason_missing():
    task = SimpleNamespace(
        task_type="exchange_cards",
        _ctx=SimpleNamespace(
            runtime=SimpleNamespace(
                delay_seconds=12,
                delay_reason=None,
            )
        ),
    )

    result, data = ExchangeDelayPostHook().run(_context(task))

    assert result == HookResult.DELAY
    assert data == {"delay_seconds": 12.0, "reason": "等待交换复查"}


def test_exchange_invalid_runtime_delay_continue():
    for delay_seconds in ("12", -1):
        task = SimpleNamespace(
            task_type="exchange_cards",
            _ctx=SimpleNamespace(
                runtime=SimpleNamespace(
                    delay_seconds=delay_seconds,
                    delay_reason="交换等待中",
                )
            ),
        )

        result, data = ExchangeDelayPostHook().run(_context(task))

        assert result == HookResult.CONTINUE
        assert data == {}


def test_non_exchange_task_continue():
    task = SimpleNamespace(
        task_type="open_pack",
        _ctx=SimpleNamespace(
            runtime=SimpleNamespace(
                delay_seconds=12,
                delay_reason="交换等待中",
            )
        ),
    )

    result, data = ExchangeDelayPostHook().run(_context(task))

    assert result == HookResult.CONTINUE
    assert data == {}
