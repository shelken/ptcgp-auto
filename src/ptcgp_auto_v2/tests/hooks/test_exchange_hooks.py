# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.hooks import HookContext, HookResult
from ptcgp_auto_v2.hooks.exchange_hooks import ExchangeDelayPostHook


class TestExchangeDelayPostHook(unittest.TestCase):
    def setUp(self):
        self.hook = ExchangeDelayPostHook()

    def test_return_delay_when_task_has_delay_seconds(self):
        task = SimpleNamespace(
            task_type="exchange_cards",
            _ctx=SimpleNamespace(
                runtime=SimpleNamespace(
                    delay_seconds=300,
                    delay_reason="等待对方回应",
                )
            ),
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1)),
            task=cast(Any, task),
            executor=cast(Any, SimpleNamespace()),
        )

        result, data = self.hook.run(context)
        self.assertEqual(HookResult.DELAY, result)
        self.assertEqual(300.0, data.get("delay_seconds"))
        self.assertEqual("等待对方回应", data.get("reason"))

    def test_continue_when_task_without_delay(self):
        task = SimpleNamespace(
            task_type="exchange_cards",
            _ctx=SimpleNamespace(runtime=SimpleNamespace(delay_seconds=None)),
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1)),
            task=cast(Any, task),
            executor=cast(Any, SimpleNamespace()),
        )

        result, data = self.hook.run(context)
        self.assertEqual(HookResult.CONTINUE, result)
        self.assertEqual({}, data)

    def test_compat_old_private_delay_fields(self):
        task = SimpleNamespace(
            task_type="exchange_cards",
            _delay_seconds=120,
            _delay_reason="兼容旧字段",
        )
        context = HookContext(
            device=cast(Any, SimpleNamespace()),
            account=cast(Any, SimpleNamespace(id=1)),
            task=cast(Any, task),
            executor=cast(Any, SimpleNamespace()),
        )

        result, data = self.hook.run(context)
        self.assertEqual(HookResult.DELAY, result)
        self.assertEqual(120.0, data.get("delay_seconds"))
        self.assertEqual("兼容旧字段", data.get("reason"))


if __name__ == "__main__":
    unittest.main()
