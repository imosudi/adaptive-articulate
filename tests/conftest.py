from typing import Generator
import pytest
from app import create_app
from app.extensions import db
from app.services.user_service import UserService


@pytest.fixture
def app_instance() -> Generator:
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app_instance) -> Generator:
    with app_instance.test_client() as client:
        yield client


@pytest.fixture
def user_service() -> UserService:
    return UserService()
