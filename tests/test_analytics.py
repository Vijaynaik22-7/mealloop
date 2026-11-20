
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Donation, DonationRequest
from app.analytics.routes import get_impact_data, CO2_KG_PER_MEAL


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


def create_provider(name, email):
    provider = User(
        name=name,
        email=email,
        role="provider",
        is_verified=True
    )
    provider.set_password("password123")
    db.session.add(provider)
    db.session.commit()
    return provider


def create_donation(provider, name, quantity, unit="meals"):
    donation = Donation(
        provider_id=provider.id,
        food_name=name,
        quantity=quantity,
        unit=unit,
        prepared_at=datetime.now() - timedelta(hours=2),
        expiry_time=datetime.now() + timedelta(hours=5),
        status="collected"
    )
    db.session.add(donation)
    db.session.commit()
    return donation


def test_impact_data(app):
    with app.app_context():
        provider = create_provider(
            "Demo Provider",
            "provider@test.com"
        )

        recipient = User(
            name="Demo NGO",
            email="ngo@test.com",
            role="recipient",
            is_verified=True,
            capacity_people=100
        )
        recipient.set_password("password123")
        db.session.add(recipient)
        db.session.commit()

        donation = create_donation(provider, "Rice", 100)

        request_record = DonationRequest(
            donation_id=donation.id,
            recipient_id=recipient.id,
            people_to_serve=80,
            status="collected",
            collected_at=datetime.utcnow()
        )
        db.session.add(request_record)
        db.session.commit()

        data = get_impact_data()

        assert data["completed_donations"] == 1
        assert data["total_meals"] == 80
        assert data["rescued_quantities"] == [
            {"unit": "meals", "quantity": 100}
        ]
        assert data["estimated_co2_saved"] == 19.04
        assert data["co2_factor"] == CO2_KG_PER_MEAL
        assert data["active_providers"] == 1
        assert data["verified_ngos"] == 1
        assert data["top_providers"][0]["name"] == "Demo Provider"
        assert data["top_providers"][0]["collected_count"] == 1


def test_top_three_providers(app):
    with app.app_context():
        provider1 = create_provider("Provider A", "a@test.com")
        provider2 = create_provider("Provider B", "b@test.com")
        provider3 = create_provider("Provider C", "c@test.com")
        provider4 = create_provider("Provider D", "d@test.com")

        create_donation(provider1, "Rice A1", 10)
        create_donation(provider1, "Rice A2", 10)
        create_donation(provider1, "Rice A3", 10)

        create_donation(provider2, "Rice B1", 10)
        create_donation(provider2, "Rice B2", 10)

        create_donation(provider3, "Rice C1", 10)
        create_donation(provider4, "Rice D1", 10)

        data = get_impact_data()

        assert len(data["top_providers"]) == 3
        assert data["top_providers"][0]["name"] == "Provider A"
        assert data["top_providers"][0]["collected_count"] == 3
        assert data["top_providers"][1]["name"] == "Provider B"
        assert data["top_providers"][2]["name"] == "Provider C"


def test_quantity_grouped_by_unit(app):
    with app.app_context():
        provider = create_provider(
            "Mixed Provider",
            "mixed@test.com"
        )

        create_donation(provider, "Rice", 50, "meals")
        create_donation(provider, "Vegetables", 5, "kg")

        data = get_impact_data()

        assert data["total_meals"] == 0
        assert data["rescued_quantities"] == [
            {"unit": "kg", "quantity": 5},
            {"unit": "meals", "quantity": 50}
        ]


def test_empty_impact_data(app):
    with app.app_context():
        data = get_impact_data()

        assert data["completed_donations"] == 0
        assert data["total_meals"] == 0
        assert data["rescued_quantities"] == []
        assert data["estimated_co2_saved"] == 0
        assert data["active_providers"] == 0
        assert data["verified_ngos"] == 0
        assert data["top_providers"] == []
