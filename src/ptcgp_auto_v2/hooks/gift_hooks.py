# -*- coding: utf-8 -*-
"""
送卡任务 Hook。

用于送卡任务前后置控制：
1. 前置：送卡前确保先执行 claim_gifts
2. 后置：送卡成功后唤醒目标账号执行回送任务
"""

from ptcgp_auto_v2.core.hooks import Hook, HookContext, HookResult
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories import TaskInstanceRepository
from ptcgp_auto_v2.services import GiftRecordService


class ClaimGiftsPreHook(Hook):
    """Hook：确保当前账号先执行领取礼物任务。"""

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """直接插入 claim_gifts 前置任务，不做额外判断。"""
        if context.account.id is None:
            return HookResult.ABORT, {
                "error": "账号ID为空，无法执行 claim_gifts 前置任务"
            }

        account_id = int(context.account.id)
        with session_scope() as session:
            repo = TaskInstanceRepository(session)
            repo.get_or_create(
                account_id=account_id,
                task_type="claim_gifts",
                reset_type="daily",
            )

        return HookResult.INSERT_TASK, {
            "task_type": "claim_gifts",
            "priority": "high",
            "reason": "领取礼物",
        }


class SendCardWakeTargetPostHook(Hook):
    """送卡成功后唤醒目标账号的送卡任务。"""

    def run(self, context: HookContext) -> tuple[HookResult, dict]:
        """若当前账号已送卡成功，则尝试唤醒目标账号回送。"""
        task = context.task
        if task.task_type != "send_card_daily":
            return HookResult.CONTINUE, {}

        gift_sent_success = bool(getattr(task, "_gift_sent_success", False))
        if not gift_sent_success:
            return HookResult.CONTINUE, {}

        target_account_id = getattr(task, "_target_account_id", None)
        if not isinstance(target_account_id, int):
            return HookResult.CONTINUE, {}

        current_friend_id = getattr(context.account, "friend_id", None)
        if not isinstance(current_friend_id, str) or not current_friend_id:
            return HookResult.CONTINUE, {}

        # 目标账号当日已给当前账号送过卡，则无需唤醒。
        if GiftRecordService.is_daily_success(
            account_id=target_account_id,
            target_friend_id=current_friend_id,
        ):
            return HookResult.CONTINUE, {}

        GiftRecordService.ensure_send_card_daily_pending(account_id=target_account_id)
        return HookResult.CONTINUE, {}
