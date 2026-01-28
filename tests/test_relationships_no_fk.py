from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.orm import selectinload

from ptcgp_auto_v2.db.models import (
    Account,
    TaskPlan,
    TaskInstance,
    AccountTaskPlan,
    PackRecord,
    PackCard,
    Card,
    CardSet,
    CardPack,
)

# 使用内存数据库
DATABASE_URL = "sqlite:///:memory:"


def test_relationships_no_fk(session: Session):
    # 1. 准备基础数据

    # Task Plan
    plan = TaskPlan(name="daily_plan", task_types='["open_pack"]')
    session.add(plan)
    session.commit()
    session.refresh(plan)

    # Account
    account = Account(
        game_id="acc_001",
        nickname="TestUser",
        task_plan_id=plan.id,  # 显式设置 ID
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    # 2. 验证 Account -> TaskPlan (One-to-Many)
    stmt = (
        select(Account)
        .where(Account.id == account.id)
        .options(selectinload(Account.task_plan))
    )
    acc_loaded = session.exec(stmt).first()
    assert acc_loaded is not None
    assert acc_loaded.task_plan is not None
    assert acc_loaded.task_plan.name == "daily_plan"
    print("✅ Account -> TaskPlan (One-to-Many) passed")

    # 3. 验证 TaskInstance -> Account (Many-to-One)
    task_instance = TaskInstance(
        account_id=account.id, task_type="open_pack", status="pending"
    )
    session.add(task_instance)
    session.commit()
    session.refresh(task_instance)

    stmt = (
        select(TaskInstance)
        .where(TaskInstance.id == task_instance.id)
        .options(selectinload(TaskInstance.account))
    )
    ti_loaded = session.exec(stmt).first()
    assert ti_loaded is not None
    assert ti_loaded.account is not None
    assert ti_loaded.account.game_id == "acc_001"
    print("✅ TaskInstance -> Account (Many-to-One) passed")

    # 4. 验证 Account -> TaskInstances (Reverse One-to-Many)
    stmt = (
        select(Account)
        .where(Account.id == account.id)
        .options(selectinload(Account.task_instances))
    )
    acc_loaded_2 = session.exec(stmt).first()
    assert len(acc_loaded_2.task_instances) > 0
    assert acc_loaded_2.task_instances[0].task_type == "open_pack"
    print("✅ Account -> TaskInstances passed")

    # 5. 验证 AccountTaskPlan (Many-to-Many Association)
    assoc = AccountTaskPlan(account_id=account.id, task_plan_id=plan.id, priority=10)
    session.add(assoc)
    session.commit()

    stmt = (
        select(Account)
        .where(Account.id == account.id)
        .options(
            selectinload(Account.task_plan_associations).selectinload(
                AccountTaskPlan.task_plan
            )
        )
    )
    acc_loaded_3 = session.exec(stmt).first()
    assert len(acc_loaded_3.task_plan_associations) > 0
    assert acc_loaded_3.task_plan_associations[0].task_plan.name == "daily_plan"
    assert acc_loaded_3.task_plan_associations[0].priority == 10
    print("✅ AccountTaskPlan (Many-to-Many) passed")

    # 6. 验证 Card System (String Keys)
    card_set = CardSet(code="A1", name="Genetic Apex")
    session.add(card_set)
    session.commit()

    card = Card(
        set_code="A1",
        number=1,
        name="Bulbasaur",
        rarity="C",
        image_url="http://example.com/1.webp",
    )
    session.add(card)
    session.commit()
    session.refresh(card)

    # 验证 Card -> CardSet
    stmt = select(Card).where(Card.id == card.id).options(selectinload(Card.card_set))
    card_loaded = session.exec(stmt).first()
    assert card_loaded.card_set is not None
    assert card_loaded.card_set.name == "Genetic Apex"
    print("✅ Card -> CardSet passed")

    # 7. 验证 PackRecord -> PackCards
    pack_record = PackRecord(account_id=account.id, pack_code="A1", pack_name="Mewtwo")
    session.add(pack_record)
    session.commit()
    session.refresh(pack_record)

    pack_card = PackCard(
        pack_record_id=pack_record.id, card_id=card.id, card_name="Bulbasaur"
    )
    session.add(pack_card)
    session.commit()

    # 验证 PackRecord -> Cards
    stmt = (
        select(PackRecord)
        .where(PackRecord.id == pack_record.id)
        .options(selectinload(PackRecord.cards))
    )
    pr_loaded = session.exec(stmt).first()
    assert len(pr_loaded.cards) == 1
    assert pr_loaded.cards[0].card_name == "Bulbasaur"

    # 验证 PackCard -> Card (Optional)
    stmt = (
        select(PackCard)
        .where(PackCard.id == pack_card.id)
        .options(selectinload(PackCard.card))
    )
    pc_loaded = session.exec(stmt).first()
    assert pc_loaded.card is not None
    assert pc_loaded.card.name == "Bulbasaur"
    print("✅ PackRecord System passed")


if __name__ == "__main__":
    # 手动运行以便快速调试
    engine = create_engine(DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        test_relationships_no_fk(s)
