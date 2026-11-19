"""End-to-end smoke test: the whole MealLoop demo flow in one test.

Flow: register provider + NGO -> NGO is blocked until the admin approves
-> provider adds food -> NGO requests -> provider accepts -> NGO marks
collected -> the Impact numbers go up.

Every step uses the real web pages (no shortcuts), like a person would.
"""
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.analytics.routes import CO2_KG_PER_MEAL, get_impact_data
from app.extensions import db
from app.models import Donation, DonationRequest, User

PASSWORD = "Secret123"


@pytest.fixture()
def app(monkeypatch):
    """A fresh app with an empty in-memory database."""
    # Make sure the email OTP feature is OFF, whatever the computer has set
    monkeypatch.delenv("OTP_ENABLED", raising=False)
    flask_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret",
    })
    yield flask_app
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


def log_in(client, email):
    """Log in through the login page and check it worked (redirect)."""
    response = client.post(
        "/auth/login", data={"email": email, "password": PASSWORD})
    assert response.status_code == 302


def test_full_demo_flow(app):
    # One browser per person, so their logins do not mix.
    provider = app.test_client()
    ngo = app.test_client()
    admin = app.test_client()

    # An admin cannot self-register, so create one directly in the database.
    with app.app_context():
        boss = User(name="Admin", email="admin@test.com", role="admin",
                    is_verified=True, email_verified=True)
        boss.set_password(PASSWORD)
        db.session.add(boss)
        db.session.commit()

    # ---- 1. Register a provider and an NGO (through the register page) ----
    response = provider.post("/auth/register", data={
        "name": "Test Canteen", "email": "canteen@test.com",
        "password": PASSWORD, "confirm_password": PASSWORD,
        "role": "provider", "phone": "9999999999", "address": "College",
    })
    assert response.status_code == 302
    response = ngo.post("/auth/register", data={
        "name": "Test NGO", "email": "ngo@test.com",
        "password": PASSWORD, "confirm_password": PASSWORD,
        "role": "recipient", "capacity_people": "50",
        "phone": "8888888888", "address": "City",
    })
    assert response.status_code == 302

    with app.app_context():
        # Providers are trusted at once; NGOs wait for the admin.
        assert User.query.filter_by(email="canteen@test.com").one().is_verified
        ngo_user = User.query.filter_by(email="ngo@test.com").one()
        assert ngo_user.is_verified is False
        ngo_id = ngo_user.id

    log_in(provider, "canteen@test.com")
    log_in(ngo, "ngo@test.com")
    log_in(admin, "admin@test.com")

    # ---- 2. Provider adds food ----
    expiry = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    prepared = datetime.now().strftime("%Y-%m-%dT%H:%M")
    response = provider.post("/provider/donations/create", data={
        "food_name": "Veg Biryani", "quantity": "10", "unit": "packets",
        "prepared_at": prepared, "expiry_time": expiry,
        "pickup_location": "Main Canteen",
    })
    assert response.status_code == 302
    with app.app_context():
        donation = Donation.query.one()
        assert donation.status == "available"
        donation_id = donation.id

    # ---- 3. An UNVERIFIED NGO is not allowed to request food ----
    response = ngo.post(f"/recipient/donations/{donation_id}/request",
                        data={"people_to_serve": "10"})
    assert response.status_code == 403

    # ---- 4. Admin approves the NGO, then the request works ----
    response = admin.post(f"/admin/recipients/{ngo_id}/approve")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, ngo_id).is_verified is True

    response = ngo.post(f"/recipient/donations/{donation_id}/request",
                        data={"people_to_serve": "10"})
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Donation, donation_id).status == "requested"
        donation_request = DonationRequest.query.one()
        assert donation_request.status == "pending"
        request_id = donation_request.id

    # ---- 5. Provider accepts ----
    response = provider.post(f"/recipient/requests/{request_id}/accept")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Donation, donation_id).status == "accepted"
        assert db.session.get(DonationRequest, request_id).status == "accepted"

    # Nothing is collected yet, so Impact is still zero.
    with app.app_context():
        assert get_impact_data()["total_meals"] == 0

    # ---- 6. NGO marks it collected ----
    response = ngo.post(f"/recipient/requests/{request_id}/collect")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Donation, donation_id).status == "collected"
        done = db.session.get(DonationRequest, request_id)
        assert done.status == "collected"
        assert done.collected_at is not None

    # ---- 7. Impact page and numbers updated ----
    assert admin.get("/analytics/impact").status_code == 200
    with app.app_context():
        data = get_impact_data()
        assert data["completed_donations"] == 1
        assert data["total_meals"] == 10
        assert data["estimated_co2_saved"] == round(10 * CO2_KG_PER_MEAL, 2)
        assert data["verified_ngos"] == 1
        assert data["top_providers"][0]["name"] == "Test Canteen"
