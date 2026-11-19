
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Donation, DonationRequest


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


@pytest.fixture
def provider(app):
    with app.app_context():
        user = User(
            name="Test Provider",
            email="provider@test.com",
            role="provider",
            is_verified=True
        )
        user.set_password("password123")

        db.session.add(user)
        db.session.commit()

        return user.id


@pytest.fixture
def another_provider(app):
    with app.app_context():
        user = User(
            name="Another Provider",
            email="another@test.com",
            role="provider",
            is_verified=True
        )
        user.set_password("password123")

        db.session.add(user)
        db.session.commit()

        return user.id


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="provider@test.com"):
    return client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "password123"
        },
        follow_redirects=True
    )


def create_test_donation(provider_id, status="available"):
    donation = Donation(
        provider_id=provider_id,
        food_name="Vegetable Rice",
        quantity=20,
        unit="plates",
        prepared_at=datetime.now(),
        expiry_time=datetime.now() + timedelta(hours=5),
        pickup_location="College Main Gate",
        status=status
    )

    db.session.add(donation)
    db.session.commit()

    return donation.id


def test_create_donation(client, app, provider):

    login(client)

    response = client.post(
        "/provider/donations/create",
        data={
            "food_name": "Vegetable Rice",
            "quantity": "20",
            "unit": "plates",
            "prepared_at": datetime.now().isoformat(
                timespec="minutes"
            ),
            "expiry_time": (
                datetime.now() + timedelta(hours=5)
            ).isoformat(timespec="minutes"),
            "pickup_location": "College Main Gate"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():
        donation = Donation.query.filter_by(
            provider_id=provider,
            food_name="Vegetable Rice"
        ).first()

        assert donation is not None
        assert donation.quantity == 20
        assert donation.status == "available"


def test_edit_own_donation(client, app, provider):

    with app.app_context():
        donation_id = create_test_donation(provider)

    login(client)

    response = client.post(
        f"/provider/donations/{donation_id}/edit",
        data={
            "food_name": "Updated Rice",
            "quantity": "30",
            "unit": "plates",
            "prepared_at": datetime.now().isoformat(
                timespec="minutes"
            ),
            "expiry_time": (
                datetime.now() + timedelta(hours=6)
            ).isoformat(timespec="minutes"),
            "pickup_location": "Updated College Gate"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():
        donation = db.session.get(Donation, donation_id)

        assert donation.food_name == "Updated Rice"
        assert donation.quantity == 30
        assert donation.pickup_location == "Updated College Gate"


def test_delete_own_donation(client, app, provider):

    with app.app_context():
        donation_id = create_test_donation(provider)

    login(client)

    response = client.post(
        f"/provider/donations/{donation_id}/delete",
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():
        donation = db.session.get(Donation, donation_id)

        assert donation is None


def test_cannot_edit_another_providers_donation(
    client, app, provider, another_provider
):

    with app.app_context():
        donation_id = create_test_donation(another_provider)

    login(client)

    response = client.get(
        f"/provider/donations/{donation_id}/edit"
    )

    assert response.status_code == 404


def test_cannot_delete_another_providers_donation(
    client, app, provider, another_provider
):

    with app.app_context():
        donation_id = create_test_donation(another_provider)

    login(client)

    response = client.post(
        f"/provider/donations/{donation_id}/delete"
    )

    assert response.status_code == 404

    with app.app_context():
        donation = db.session.get(Donation, donation_id)

        assert donation is not None


def test_cannot_edit_non_available_donation(
    client, app, provider
):

    with app.app_context():
        donation_id = create_test_donation(
            provider,
            status="collected"
        )

    login(client)

    response = client.get(
        f"/provider/donations/{donation_id}/edit",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Only available donations can be edited." in response.data


def test_cannot_delete_non_available_donation(
    client, app, provider
):

    with app.app_context():
        donation_id = create_test_donation(
            provider,
            status="collected"
        )

    login(client)

    response = client.post(
        f"/provider/donations/{donation_id}/delete",
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Only available donations can be deleted." in response.data

    with app.app_context():
        donation = db.session.get(Donation, donation_id)

        assert donation is not None


def test_provider_can_view_own_donation_requests(
    client, app, provider
):
    with app.app_context():
        recipient = User(
            name="Test NGO",
            email="ngo@test.com",
            role="recipient",
            is_verified=True,
            capacity_people=100
        )
        recipient.set_password("password123")

        db.session.add(recipient)
        db.session.commit()

        donation_id = create_test_donation(provider)

        donation_request = DonationRequest(
            donation_id=donation_id,
            recipient_id=recipient.id,
            people_to_serve=25,
            status="pending",
            priority_score=85.0
        )

        db.session.add(donation_request)
        db.session.commit()

    login(client)

    response = client.get(
        f"/provider/donations/{donation_id}/requests"
    )

    assert response.status_code == 200
    assert b"Donation Requests" in response.data
    assert b"Test NGO" in response.data
    assert b"25" in response.data


def test_provider_cannot_view_another_providers_requests(
    client, app, provider, another_provider
):
    with app.app_context():
        donation_id = create_test_donation(another_provider)

    login(client)

    response = client.get(
        f"/provider/donations/{donation_id}/requests"
    )

    assert response.status_code == 404


def test_provider_sees_empty_requests_message(client, app, provider):
    with app.app_context():
        donation_id = create_test_donation(provider)

    login(client)

    response = client.get(
        f"/provider/donations/{donation_id}/requests"
    )

    assert response.status_code == 200
    assert b"No requests have been received" in response.data


def test_create_donation_with_coordinates(client, app, provider):
    login(client)

    response = client.post(
        "/provider/donations/create",
        data={
            "food_name": "Vegetable Rice",
            "quantity": "20",
            "unit": "plates",
            "prepared_at": datetime.now().isoformat(timespec="minutes"),
            "expiry_time": (
                datetime.now() + timedelta(hours=5)
            ).isoformat(timespec="minutes"),
            "pickup_location": "College Main Gate",
            "latitude": "12.9716",
            "longitude": "77.5946"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():
        donation = Donation.query.filter_by(
            provider_id=provider,
            food_name="Vegetable Rice"
        ).first()

        assert donation.latitude == pytest.approx(12.9716)
        assert donation.longitude == pytest.approx(77.5946)


def test_create_donation_without_coordinates(client, app, provider):
    login(client)

    response = client.post(
        "/provider/donations/create",
        data={
            "food_name": "Plain Rice",
            "quantity": "10",
            "unit": "plates",
            "prepared_at": datetime.now().isoformat(timespec="minutes"),
            "expiry_time": (
                datetime.now() + timedelta(hours=5)
            ).isoformat(timespec="minutes"),
            "pickup_location": "College Main Gate",
            "latitude": "",
            "longitude": ""
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():
        donation = Donation.query.filter_by(
            provider_id=provider,
            food_name="Plain Rice"
        ).first()

        assert donation is not None
        assert donation.latitude is None
        assert donation.longitude is None


def test_create_donation_rejects_invalid_coordinates(
    client, app, provider
):
    login(client)

    response = client.post(
        "/provider/donations/create",
        data={
            "food_name": "Invalid Location Rice",
            "quantity": "10",
            "unit": "plates",
            "prepared_at": datetime.now().isoformat(timespec="minutes"),
            "expiry_time": (
                datetime.now() + timedelta(hours=5)
            ).isoformat(timespec="minutes"),
            "pickup_location": "College Main Gate",
            "latitude": "95",
            "longitude": "77.5946"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"coordinates" in response.data.lower()

    with app.app_context():
        donation = Donation.query.filter_by(
            provider_id=provider,
            food_name="Invalid Location Rice"
        ).first()

        assert donation is None


def test_edit_donation_updates_coordinates(client, app, provider):
    with app.app_context():
        donation_id = create_test_donation(provider)

    login(client)

    response = client.post(
        f"/provider/donations/{donation_id}/edit",
        data={
            "food_name": "Updated Rice",
            "quantity": "30",
            "unit": "plates",
            "prepared_at": datetime.now().isoformat(timespec="minutes"),
            "expiry_time": (
                datetime.now() + timedelta(hours=6)
            ).isoformat(timespec="minutes"),
            "pickup_location": "Updated College Gate",
            "latitude": "13.0827",
            "longitude": "80.2707"
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with app.app_context():
        donation = db.session.get(Donation, donation_id)

        assert donation.latitude == pytest.approx(13.0827)
        assert donation.longitude == pytest.approx(80.2707)


def test_provider_expiry_badges():
    from app.providers.expiry import expiry_badge

    now = datetime(2026, 11, 19, 12, 0)

    assert expiry_badge(now - timedelta(minutes=1), now)["text"] == "Expired"
    soon = expiry_badge(now + timedelta(minutes=45), now)
    assert soon["text"] == "Expiring soon · 45m"
    assert "warning" in soon["css"]
    later = expiry_badge(now + timedelta(hours=3), now)
    assert later["text"] == "Expires in 3h"
    assert later["css"] == "bg-success"


def test_provider_dashboard_displays_expiry_badge(client, app, provider):
    with app.app_context():
        create_test_donation(provider)

    login(client)
    response = client.get("/provider/dashboard")

    assert response.status_code == 200
    assert b"Expires in" in response.data
