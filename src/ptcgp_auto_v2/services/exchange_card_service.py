# -*- coding: utf-8 -*-
"""
交换卡牌业务服务

封装交换卡牌请求创建与状态推进的业务规则。
"""

from datetime import datetime, timedelta
from typing import Optional

from ptcgp_auto_v2.db.models import ExchangeCardRequest
from ptcgp_auto_v2.db.repositories import (
    AccountRepository,
    ExchangeCardRequestRepository,
)
from ptcgp_auto_v2.config.rarity_icons import RARITY_META


class ExchangeCardService:
    """交换卡牌业务服务。"""

    DEFAULT_EXPIRE_MINUTES = 5

    @classmethod
    def get_required_exchange_points(cls, rarity_code: str) -> Optional[int]:
        """根据稀有度返回所需交换点数（从 RARITY_META 获取）。"""
        normalized_rarity = (rarity_code or "").upper()
        meta = RARITY_META.get(normalized_rarity)
        if meta:
            return meta.get("exchange_cost")
        return None

    @classmethod
    def is_exchangeable(cls, rarity_code: str) -> bool:
        """检查稀有度是否可交换（从 RARITY_META 获取）。"""
        normalized_rarity = (rarity_code or "").upper()
        meta = RARITY_META.get(normalized_rarity)
        return meta.get("exchangeable", False) if meta else False

    @classmethod
    def create_request(
        cls,
        from_account_id: int,
        to_friend_id: str,
        target_card_id: int,
        target_card_rarity: str,
        to_account_id: Optional[int] = None,
        to_nickname: Optional[str] = None,
    ) -> Optional[ExchangeCardRequest]:
        """创建交换请求；不允许 IM/UR 稀有度。"""
        normalized_rarity = (target_card_rarity or "").upper()
        if not cls.is_exchangeable(normalized_rarity):
            return None

        required_points = cls.get_required_exchange_points(normalized_rarity)
        if required_points is None:
            return None

        account = AccountRepository().get_by_id(from_account_id)
        if account is None:
            return None
        current_points = int(account.exchange_points or 0)
        if current_points < required_points:
            return None

        repo = ExchangeCardRequestRepository()
        if repo.has_active_request(from_account_id):
            return None

        request = repo.create(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            to_nickname=to_nickname,
            to_friend_id=to_friend_id,
            target_card_id=target_card_id,
            target_card_rarity=normalized_rarity,
            status="sending",
        )
        if request is None:
            return None
        request.expire_at = datetime.now() + timedelta(
            minutes=cls.DEFAULT_EXPIRE_MINUTES
        )
        return repo.update(request)
