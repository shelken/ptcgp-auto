# -*- coding: utf-8 -*-
"""
账号送卡执行记录模型。

用于记录每日送卡执行状态、目标和库存同步信息。
"""

from typing import Optional, ClassVar

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .base import TimestampMixin
from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str


def _today_local_date() -> str:
    """返回游戏业务日期字符串 YYYY-MM-DD（按 UTC06:00 换算本地切日）。"""
    return get_game_biz_date_str()


class AccountGiftRecord(SQLModel, TimestampMixin, table=True):
    """
    账号送卡执行记录表。

    第一性语义：
    - 这张表记录「一次业务日内，对某个目标执行送卡」的结果。
    - `account_gift_pairs` 决定今天应该送给谁；本表记录今天实际有没有送、送到哪一步、是否成功。
    - 即使后续固定配对被人工调整，历史执行记录也必须保持当时目标快照不变。
    """

    __tablename__: ClassVar[str] = "account_gift_records"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "target_friend_id",
            "biz_date_local",
            name="uq_gift_record_account_target_day",
        ),
    )

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="执行记录主键，仅用于唯一标识一次送卡流水",
    )
    account_id: int = Field(
        index=True,
        description="送卡发起账号 ID；与目标和业务日共同构成单日唯一记录",
    )
    target_account_id: Optional[int] = Field(
        default=None,
        index=True,
        description="目标账号 ID（系统内账号）；便于回送统计和 Web 聚合进度",
    )
    target_friend_id: str = Field(
        index=True,
        description="目标 friend_id 快照；即使后续配对调整，历史记录仍保留当次目标",
    )

    card_id: Optional[int] = Field(
        default=None,
        index=True,
        description="送出的卡牌 ID；成功收敛后用于同步双方库存",
    )
    card_set_code: Optional[str] = Field(
        default=None,
        description="送出的卡牌系列代码；保留轻量快照，便于查询与排查",
    )
    card_number: Optional[int] = Field(
        default=None,
        description="送出的卡牌编号；与 series 一起用于页面展示和审计",
    )

    before_count: Optional[int] = Field(
        default=None,
        description="送卡前持有数量；优先来自 UI 识别，用于验证库存扣减是否符合预期",
    )
    after_count: Optional[int] = Field(
        default=None,
        description="送卡后持有数量；成功后回写 account_cards 时以该值为准",
    )
    count_source: Optional[str] = Field(
        default=None,
        description="数量来源(ui/fallback/db)；用于区分真实识别与兜底推导",
    )

    status: str = Field(
        default="init",
        index=True,
        description="送卡状态机当前节点；用于区分未开始、进行中、成功和各类完成态",
    )
    error_code: Optional[str] = Field(
        default=None,
        index=True,
        description="失败或完成收敛错误码；给聚合统计和后续排查一个稳定键",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="失败详情或完成原因文本；便于直接查看当次收敛结果",
    )

    biz_date_local: str = Field(
        default_factory=_today_local_date,
        index=True,
        description="业务日期；单日唯一键的一部分，保证同一目标每天只保留一条记录",
    )
