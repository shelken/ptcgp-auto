"""initial schema baseline

初始 schema 基线版本

该版本标记现有数据库结构为基线，不包含实际迁移操作。
后续的 schema 变更将基于此版本生成增量迁移脚本。

Revision ID: 331afd912809
Revises:
Create Date: 2026-01-22 20:09:05.408673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '331afd912809'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema（空操作，仅作为基线）"""
    pass


def downgrade() -> None:
    """降级 schema（空操作，仅作为基线）"""
    pass
