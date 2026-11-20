"""Expiry also covers requested donations and rejects their requests."""
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.matching.priority import expire_old_donations
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


def make_donation(provider_id, status, hours_from_now):
    """A donation that expires `hours_from_now` hours from now."""
    now = datetime.now()
    return Donation(
        provider_id=provider_id, food_name="Rice", quantity=20,
        unit="packets", prepared_at=now - timedelta(hours=3),
        expiry_time=now + timedelta(hours=hours_from_now), status=status)


def make_users():
    provider = User(name="P", email="p@test.com", role="provider",
                    is_verified=True)
    provider.set_password("pass1234")
    ngo = User(name="N", email="n@test.com", role="recipient",
               capacity_people=100, is_verified=True)
    ngo.set_password("pass1234")
    db.session.add_all([provider, ngo])
    db.session.commit()
    return provider, ngo


def test_requested_donation_expires_and_request_is_rejected(app):
    with app.app_context():
        provider, ngo = make_users()
        donation = make_donation(provider.id, "requested", -1)
        db.session.add(donation)
        db.session.commit()
        req = DonationRequest(donation_id=donation.id, recipient_id=ngo.id,
                              people_to_serve=10, status="pending")
        db.session.add(req)
        db.session.commit()

        count = expire_old_donations(db.session)

        assert count == 1
        assert db.session.get(Donation, donation.id).status == "expired"
        assert db.session.get(DonationRequest, req.id).status == "rejected"


def test_fresh_requested_donation_is_untouched(app):
    with app.app_context():
        provider, ngo = make_users()
        donation = make_donation(provider.id, "requested", 5)
        db.session.add(donation)
        db.session.commit()
        req = DonationRequest(donation_id=donation.id, recipient_id=ngo.id,
                              people_to_serve=10, status="pending")
        db.session.add(req)
        db.session.commit()

        assert expire_old_donations(db.session) == 0
        assert db.session.get(Donation, donation.id).status == "requested"
        assert db.session.get(DonationRequest, req.id).status == "pending"


def test_accepted_donation_is_not_expired(app):
    with app.app_context():
        provider, ngo = make_users()
        donation = make_donation(provider.id, "accepted", -1)
        db.session.add(donation)
        db.session.commit()

        assert expire_old_donations(db.session) == 0
        assert db.session.get(Donation, donation.id).status == "accepted"
