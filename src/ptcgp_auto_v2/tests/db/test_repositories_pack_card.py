import pytest
from unittest.mock import patch
from sqlmodel import Session, SQLModel, create_engine
from datetime import datetime

from ptcgp_auto_v2.db.models import Account, Card, CardSet, PackRecord, PackCard
from ptcgp_auto_v2.db.repositories import CardRepository, PackRecordRepository


pytestmark = pytest.mark.usefixtures("mock_get_engine")


# Create a fresh in-memory database for each test
@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="mock_get_engine")
def mock_get_engine_fixture(engine):
    with (
        patch(
            "ptcgp_auto_v2.db.repositories.card_repository.get_engine",
            return_value=engine,
        ),
        patch(
            "ptcgp_auto_v2.db.repositories.pack_record_repository.get_engine",
            return_value=engine,
        ),
    ):
        yield


def seed_data(engine):
    with Session(engine) as session:
        # Create Account
        account = Account(game_id="test_game_id", nickname="TestUser")
        session.add(account)

        # Create CardSet
        card_set = CardSet(code="A1", name="Genetic Apex", total_cards=200)
        session.add(card_set)

        # Create Cards
        c1 = Card(
            set_code="A1",
            number=1,
            name="Bulbasaur",
            rarity="diamond_1",
            image_url="url1",
        )
        c2 = Card(
            set_code="A1",
            number=25,
            name="Pikachu",
            rarity="diamond_2",
            image_url="url2",
        )
        session.add(c1)
        session.add(c2)

        session.commit()
        # Return account.id. Since session is closed, we return the scalar ID.
        return account.id


class TestCardRepository:
    def test_get_card_by_template_name_valid_format(self, engine):
        seed_data(engine)
        repo = CardRepository()

        # Test "001_Bulbasaur.png" format
        card = repo.get_card_by_template_name("A1", "001_Bulbasaur.png")
        assert card is not None
        assert card.number == 1
        assert card.name == "Bulbasaur"

    def test_get_card_by_template_name_simple_number(self, engine):
        seed_data(engine)
        repo = CardRepository()

        # Test "025" format
        card = repo.get_card_by_template_name("A1", "025")
        assert card is not None
        assert card.number == 25
        assert card.name == "Pikachu"

    def test_get_card_by_template_name_invalid_format(self, engine):
        seed_data(engine)
        repo = CardRepository()

        # Test invalid string
        card = repo.get_card_by_template_name("A1", "Bulbasaur")
        assert card is None

        # Test non-existent number
        card = repo.get_card_by_template_name("A1", "999_Unknown")
        assert card is None


class TestPackRecordRepository:
    def test_get_today_should_use_game_day_window(self, engine):
        account_id = seed_data(engine)
        assert account_id is not None
        repo = PackRecordRepository()

        with Session(engine) as session:
            session.add(
                PackRecord(
                    account_id=account_id,
                    pack_type="daily_free",
                    opened_at=datetime(2026, 2, 15, 13, 30, 0),
                )
            )
            session.add(
                PackRecord(
                    account_id=account_id,
                    pack_type="daily_free",
                    opened_at=datetime(2026, 2, 15, 14, 30, 0),
                )
            )
            session.commit()

        with patch(
            "ptcgp_auto_v2.db.repositories.pack_record_repository.get_game_day_window",
            return_value=(
                datetime(2026, 2, 15, 14, 0, 0),
                datetime(2026, 2, 16, 14, 0, 0),
            ),
        ):
            record = repo.get_today(account_id)

        assert record is not None
        assert record.opened_at == datetime(2026, 2, 15, 14, 30, 0)

    def test_has_opened_today_should_use_game_day_window(self, engine):
        account_id = seed_data(engine)
        assert account_id is not None
        repo = PackRecordRepository()

        with Session(engine) as session:
            session.add(
                PackRecord(
                    account_id=account_id,
                    pack_type="daily_free",
                    opened_at=datetime(2026, 2, 15, 14, 1, 0),
                )
            )
            session.commit()

        with patch(
            "ptcgp_auto_v2.db.repositories.pack_record_repository.get_game_day_window",
            return_value=(
                datetime(2026, 2, 15, 14, 0, 0),
                datetime(2026, 2, 16, 14, 0, 0),
            ),
        ):
            assert repo.has_opened_today(account_id) is True

    def test_create_for_account_with_cards(self, engine):
        account_id = seed_data(engine)
        repo = PackRecordRepository()

        # Get actual card ID from DB
        with Session(engine) as s:
            real_card = s.query(Card).filter(Card.number == 1).first()
            assert real_card is not None
            real_card_id = real_card.id
            assert real_card_id is not None

        # Prepare card data
        cards_data = [
            {
                "card_id": real_card_id,
                "card_name": "Bulbasaur",
                "rarity": "diamond_1",
                "is_new": True,
                "position": 1,
                "confidence": 0.95,
            },
            {
                "card_id": None,  # Unmatched card
                "card_name": "Unknown Card",
                "rarity": "star_1",
                "is_new": False,
                "position": 2,
            },
        ]

        # Execute
        record = repo.create_for_account(
            account_id=account_id, pack_type="Mewtwo", cards=cards_data
        )

        # Verify PackRecord
        assert record.id is not None
        assert record.account_id == account_id
        assert record.pack_type == "Mewtwo"

        # Verify PackCards
        with Session(engine) as session:
            # Re-fetch record with relationship loaded
            saved_record = session.get(PackRecord, record.id)
            assert saved_record is not None
            assert len(saved_record.cards) == 2

            # Check first card
            # Since order isn't strictly guaranteed without order_by, we find by name
            c1 = next(c for c in saved_record.cards if c.card_name == "Bulbasaur")
            assert c1.card_id == real_card_id
            assert c1.is_new is True
            assert c1.position == 1
            assert abs(c1.confidence - 0.95) < 0.001

            # Check second card
            c2 = next(c for c in saved_record.cards if c.card_name == "Unknown Card")
            assert c2.card_id is None
            assert c2.rarity == "star_1"
