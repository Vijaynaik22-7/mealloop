
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Donation
from app.analytics.routes import get_impact_data


@pytest.fixture
def app():
    test_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret"
    })

    with test_app.app_context():
        db.drop_all()
        db.create_all()

        yield test_app

        db.session.remove()
        db.drop_all()


def test_impact_data(app):
    with app.app_context():

        provider = User(
            name="Demo Provider",
            email="provider@test.com",
            role="provider",
            is_verified=True
        )
        provider.set_password("password123")

        recipient = User(
            name="Demo NGO",
            email="ngo@test.com",
            role="recipient",
            is_verified=True,
            capacity_people=100
        )
        recipient.set_password("password123")

        db.session.add_all([provider, recipient])
        db.session.commit()

        donation = Donation(
            provider_id=provider.id,
            food_name="Rice",
            quantity=100,
            unit="meals",
            prepared_at=datetime.utcnow() - timedelta(hours=2),
            expiry_time=datetime.utcnow() + timedelta(hours=5),
            status="collected"
        )

        db.session.add(donation)
        db.session.commit()

        data = get_impact_data()

        assert data["completed_donations"] == 1
        assert data["total_meals"] == 100
        assert data["waste_avoided"] == 25.0
        assert data["active_providers"] == 1
        assert data["verified_ngos"] == 1


def test_empty_impact_data(app):
    with app.app_context():

        data = get_impact_data()

        assert data["completed_donations"] == 0
        assert data["total_meals"] == 0
        assert data["waste_avoided"] == 0
        assert data["active_providers"] == 0
        assert data["verified_ngos"] == 0
