# -*- coding: utf-8 -*-
"""交换卡牌任务 Hook。"""

from ptcgp_auto_v2.core.hooks import Hook, HookContext, HookResult


class ExchangeDelayPostHook(Hook):
    """交换任务后置延时 Hook。"""

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """根据任务阶段返回下次复查延时。"""
        task = context.task
        if task.task_type != "exchange_cards":
            return HookResult.CONTINUE, {}

        delay_seconds = getattr(task, "_delay_seconds", None)
        if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
            return HookResult.CONTINUE, {}

        reason = getattr(task, "_delay_reason", None) or "等待交换复查"
        return HookResult.DELAY, {
            "delay_seconds": float(delay_seconds),
            "reason": reason,
        }
