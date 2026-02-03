import pytest
from sqlmodel import Session, SQLModel, create_engine


def _create_in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture():
    engine = _create_in_memory_engine()
    with Session(engine) as session:
        yield session
