# -*- coding: utf-8 -*-
"""
交换卡牌业务服务

封装交换卡牌请求创建与状态推进的业务规则。
"""

from datetime import datetime, timedelta
from typing import Optional

from ptcgp_auto_v2.db.models import ExchangeCardRequest
from ptcgp_auto_v2.db.repositories import ExchangeCardRequestRepository


class ExchangeCardService:
    """交换卡牌业务服务。"""

    EXCHANGE_POINT_COSTS = {
        "C": 0,
        "U": 0,
        "R": 1200,
        "RR": 5000,
        "AR": 4000,
        "SR": 25000,
        "SAR": 25000,
        "S": 10000,
        "SSR": 30000,
    }
    NON_EXCHANGEABLE_RARITIES = {"IM", "UR"}
    DEFAULT_EXPIRE_MINUTES = 5

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
        if normalized_rarity in cls.NON_EXCHANGEABLE_RARITIES:
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
