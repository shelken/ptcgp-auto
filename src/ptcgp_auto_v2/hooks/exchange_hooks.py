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

        runtime = getattr(getattr(task, "_ctx", None), "runtime", None)
        delay_seconds = getattr(runtime, "delay_seconds", None)
        delay_reason = getattr(runtime, "delay_reason", None)

        # 兼容旧字段，避免历史测试桩或旧实现失效。
        if not isinstance(delay_seconds, (int, float)):
            delay_seconds = getattr(task, "_delay_seconds", None)
        if not delay_reason:
            delay_reason = getattr(task, "_delay_reason", None)

        if not isinstance(delay_seconds, (int, float)) or delay_seconds < 0:
            return HookResult.CONTINUE, {}

        reason = delay_reason or "等待交换复查"
        return HookResult.DELAY, {
            "delay_seconds": float(delay_seconds),
            "reason": reason,
        }
