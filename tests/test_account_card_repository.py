# -*- coding: utf-8 -*-

from sqlmodel import SQLModel, create_engine

from ptcgp_auto_v2.db import engine as db_engine
from ptcgp_auto_v2.db.repositories import AccountCardRepository


def test_account_card_upsert():
    db_engine._engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(db_engine._engine)

    repo = AccountCardRepository()
    repo.upsert(account_id=1, card_id=10, count=1)
    repo.upsert(account_id=1, card_id=10, count=1)

    row = repo.get(account_id=1, card_id=10)
    assert row is not None
    assert row.count == 1
