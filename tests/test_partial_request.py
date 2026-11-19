"""Partial requests: the part the NGO did not ask for stays available."""
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Donation, DonationRequest, User


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def make_case(app, quantity, people):
    """One provider, one NGO, one donation and one pending request.

    Returns (provider_id, donation_id, request_id).
    """
    now = datetime.utcnow()
    with app.app_context():
        provider = User(
            name="Provider", email="p@test.com", role="provider",
            password_hash=generate_password_hash("pass1234"),
            is_verified=True,
        )
        ngo = User(
            name="Ngo", email="n@test.com", role="recipient",
            password_hash=generate_password_hash("pass1234"),
            capacity_people=500, is_verified=True,
        )
        db.session.add_all([provider, ngo])
        db.session.commit()
        donation = Donation(
            provider_id=provider.id, food_name="Biryani", quantity=quantity,
            unit="packets", prepared_at=now - timedelta(hours=1),
            expiry_time=now + timedelta(hours=5),
            pickup_location="Main Canteen", status="requested",
        )
        db.session.add(donation)
        db.session.commit()
        req = DonationRequest(
            donation_id=donation.id, recipient_id=ngo.id,
            people_to_serve=people, status="pending", priority_score=0.0,
        )
        db.session.add(req)
        db.session.commit()
        return provider.id, donation.id, req.id


def accept(app, provider_id, request_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(provider_id)
        sess["_fresh"] = True
    return client.post(f"/recipient/requests/{request_id}/accept")


def test_partial_request_leaves_the_rest_available(app):
    provider_id, donation_id, request_id = make_case(app, 70, 50)

    assert accept(app, provider_id, request_id).status_code == 302

    with app.app_context():
        accepted = db.session.get(Donation, donation_id)
        assert accepted.quantity == 50
        assert accepted.status == "accepted"
        assert Donation.query.count() == 2
        leftover = Donation.query.filter(Donation.id != donation_id).one()
        assert leftover.quantity == 20
        assert leftover.status == "available"
        assert leftover.provider_id == provider_id
        assert leftover.food_name == "Biryani"
        assert leftover.expiry_time == accepted.expiry_time


def test_exact_request_does_not_split(app):
    provider_id, donation_id, request_id = make_case(app, 10, 10)

    accept(app, provider_id, request_id)

    with app.app_context():
        assert Donation.query.count() == 1
        assert db.session.get(Donation, donation_id).quantity == 10


def test_request_bigger_than_stock_takes_everything(app):
    provider_id, donation_id, request_id = make_case(app, 10, 20)

    accept(app, provider_id, request_id)

    with app.app_context():
        assert Donation.query.count() == 1
        donation = db.session.get(Donation, donation_id)
        assert donation.quantity == 10
        assert donation.status == "accepted"
