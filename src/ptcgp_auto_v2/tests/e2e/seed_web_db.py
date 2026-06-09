"""Web 浏览器 E2E deterministic fixture seed。"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

from ptcgp_auto_v2.config.settings import get_project_root
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import (
    Account,
    AccountCard,
    AccountPackPoint,
    AccountStat,
    Card,
    CardPack,
    CardSet,
    Pack,
    PackCard,
    PackRecord,
    PackRecordType,
)
from ptcgp_auto_v2.tests.e2e.harness import rebind_test_runtime


def _label(en: str, zh: str) -> str:
    return json.dumps({"en": en, "zh_CN": zh}, ensure_ascii=False)


def _card_data(en: str, zh: str) -> str:
    return json.dumps({"name": {"en": en, "zh_CN": zh}}, ensure_ascii=False)


def _add_pack_record(
    *,
    account_id: int,
    set_code: str,
    pack_name: str,
    opened_at: datetime,
    card_id: int,
    card_name: str,
    rarity: str,
) -> None:
    record = PackRecord(
        account_id=account_id,
        pack_type=PackRecordType.DAILY_FREE,
        pack_code=set_code,
        pack_name=pack_name,
        opened_at=opened_at,
    )
    with session_scope() as session:
        session.add(record)
        session.flush()
        if record.id is None:
            raise RuntimeError("Web E2E seed pack record id 为空")
        session.add(
            PackCard(
                pack_record_id=record.id,
                card_id=card_id,
                card_name=card_name,
                rarity=rarity,
                is_new=True,
                position=1,
                confidence=1.0,
            )
        )


def seed_web_e2e_db(db_path: Path) -> None:
    """创建 Web E2E 最小完整数据集。"""
    db_path = validate_web_e2e_db_path(db_path)
    # 变更原因：seed 函数本身也是写库边界，直接调用时也必须拒绝真实运行库。
    rebind_test_runtime(db_path, [])
    now = datetime.now().replace(microsecond=0)

    with session_scope() as session:
        account = Account(
            game_id="web_e2e_game_001",
            friend_id="1111222233334444",
            nickname="Web E2E Account",
            xml_content=b"web-e2e",
            country="SG",
        )
        session.add(account)
        session.flush()
        if account.id is None:
            raise RuntimeError("Web E2E seed account id 为空")

        session.add(
            AccountStat(
                account_id=account.id,
                exchange_points=5000,
                pack_hourglass_count=12,
            )
        )
        session.add_all(
            [
                CardSet(
                    code="A1",
                    name="Genetic Apex",
                    release_date="2024-10-30",
                    total_cards=2,
                    label_data=_label("A1 Genetic Apex", "A1 最强的基因"),
                ),
                CardSet(
                    code="A2",
                    name="Space-Time Smackdown",
                    release_date="2025-01-30",
                    total_cards=2,
                    label_data=_label("A2 Space-Time Smackdown", "A2 时空激斗"),
                ),
                Pack(
                    name="web-e2e-a1-pack",
                    set_code="A1",
                    label_data=_label("A1 Fixture Pack", "A1 测试卡包"),
                ),
                Pack(
                    name="web-e2e-a2-pack",
                    set_code="A2",
                    label_data=_label("A2 Fixture Pack", "A2 测试卡包"),
                ),
            ]
        )
        session.flush()

        pikachu = Card(
            set_code="A1",
            number=1,
            name="Pikachu",
            rarity="C",
            image_url="web-e2e-pikachu.webp",
            element="lightning",
            type="pokemon",
            data=_card_data("Pikachu", "皮卡丘"),
        )
        mewtwo = Card(
            set_code="A1",
            number=2,
            name="Mewtwo",
            rarity="R",
            image_url="web-e2e-mewtwo.webp",
            element="psychic",
            type="pokemon",
            data=_card_data("Mewtwo", "超梦"),
        )
        charizard = Card(
            set_code="A2",
            number=1,
            name="Charizard",
            rarity="U",
            image_url="web-e2e-charizard.webp",
            element="fire",
            type="pokemon",
            data=_card_data("Charizard", "喷火龙"),
        )
        eevee = Card(
            set_code="A2",
            number=2,
            name="Eevee",
            rarity="C",
            image_url="web-e2e-eevee.webp",
            element="colorless",
            type="pokemon",
            data=_card_data("Eevee", "伊布"),
        )
        session.add_all([pikachu, mewtwo, charizard, eevee])
        session.flush()
        for card in [pikachu, mewtwo, charizard, eevee]:
            if card.id is None:
                raise RuntimeError(f"Web E2E seed card id 为空: {card.name}")

        session.add_all(
            [
                CardPack(card_id=pikachu.id, pack_name="web-e2e-a1-pack"),
                CardPack(card_id=mewtwo.id, pack_name="web-e2e-a1-pack"),
                CardPack(card_id=charizard.id, pack_name="web-e2e-a2-pack"),
                CardPack(card_id=eevee.id, pack_name="web-e2e-a2-pack"),
                AccountCard(account_id=account.id, card_id=pikachu.id, count=2),
                AccountCard(account_id=account.id, card_id=charizard.id, count=1),
                AccountCard(account_id=account.id, card_id=eevee.id, count=3),
                AccountPackPoint(account_id=account.id, series="A1", points=111),
                AccountPackPoint(account_id=account.id, series="A2", points=222),
            ]
        )
        account_id = account.id
        pikachu_id = pikachu.id
        charizard_id = charizard.id

    _add_pack_record(
        account_id=account_id,
        set_code="A1",
        pack_name="web-e2e-a1-pack",
        opened_at=now - timedelta(minutes=2),
        card_id=pikachu_id,
        card_name="Pikachu",
        rarity="C",
    )
    _add_pack_record(
        account_id=account_id,
        set_code="A2",
        pack_name="web-e2e-a2-pack",
        opened_at=now - timedelta(minutes=1),
        card_id=charizard_id,
        card_name="Charizard",
        rarity="U",
    )


def validate_web_e2e_db_path(db_path: Path) -> Path:
    """拒绝会误删/误连真实运行库的 Web E2E DB 路径。"""
    resolved = db_path.expanduser().resolve()
    project_root = get_project_root().resolve()
    default_db = (project_root / "data" / "ptcgp_v2.db").resolve()
    if resolved == default_db:
        raise RuntimeError("Web E2E 禁止使用默认数据库 data/ptcgp_v2.db")
    if project_root in resolved.parents and "web-e2e" not in resolved.name:
        raise RuntimeError("项目目录内 Web E2E 数据库文件名必须包含 web-e2e")
    if "web-e2e" not in resolved.name:
        raise RuntimeError("Web E2E 数据库文件名必须包含 web-e2e")
    return resolved


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("用法: uv run python -m ptcgp_auto_v2.tests.e2e.seed_web_db <db_path>", file=sys.stderr)
        return 2
    db_path = validate_web_e2e_db_path(Path(args[0]))
    if db_path.exists():
        # 变更原因：只允许清理显式命名的 Web E2E 临时库，避免误删真实运行库。
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    seed_web_e2e_db(db_path)
    print(f"Web E2E fixture 已写入: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
