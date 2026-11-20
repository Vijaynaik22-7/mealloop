
"""Tests for MealLoop donation priority and expiry."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from app import create_app
from app.extensions import db
from app.models import User, Donation
from app.matching.priority import (
    calculate_priority_score,
    calculate_distance,
    expire_old_donations,
)


def make_donation(
    now,
    expiry_hours=10,
    quantity=100,
    latitude=12.30,
    longitude=76.65
):
    return SimpleNamespace(
        prepared_at=now - timedelta(hours=2),
        created_at=now - timedelta(hours=2),
        expiry_time=now + timedelta(hours=expiry_hours),
        quantity=quantity,
        latitude=latitude,
        longitude=longitude,
        status="available"
    )


def make_recipient(
    capacity=100,
    latitude=12.30,
    longitude=76.65
):
    return SimpleNamespace(
        capacity_people=capacity,
        latitude=latitude,
        longitude=longitude
    )


def test_distance_same_location():
    distance = calculate_distance(
        12.30, 76.65,
        12.30, 76.65
    )
    assert distance == 0


def test_expired_donation_score_is_zero():
    now = datetime.now()

    donation = make_donation(now)
    donation.expiry_time = now - timedelta(hours=1)

    recipient = make_recipient()

    score = calculate_priority_score(
        donation, recipient, now
    )

    assert score == 0.0


def test_score_is_between_zero_and_hundred():
    now = datetime.now()

    donation = make_donation(now)
    recipient = make_recipient()

    score = calculate_priority_score(
        donation, recipient, now
    )

    assert 0 <= score <= 100


def test_near_recipient_gets_higher_score():
    now = datetime.now()

    donation = make_donation(now)

    near_recipient = make_recipient(
        latitude=12.30,
        longitude=76.65
    )

    far_recipient = make_recipient(
        latitude=13.30,
        longitude=77.65
    )

    near_score = calculate_priority_score(
        donation, near_recipient, now
    )

    far_score = calculate_priority_score(
        donation, far_recipient, now
    )

    assert near_score > far_score


def test_urgent_donation_gets_higher_score():
    now = datetime.now()

    urgent_donation = make_donation(
        now,
        expiry_hours=3
    )

    less_urgent_donation = make_donation(
        now,
        expiry_hours=10
    )

    recipient = make_recipient()

    urgent_score = calculate_priority_score(
        urgent_donation, recipient, now
    )

    less_urgent_score = calculate_priority_score(
        less_urgent_donation, recipient, now
    )

    assert urgent_score > less_urgent_score


def test_better_capacity_fit_gets_higher_score():
    now = datetime.now()

    donation = make_donation(
        now,
        quantity=100
    )

    good_capacity = make_recipient(
        capacity=100
    )

    low_capacity = make_recipient(
        capacity=50
    )

    good_score = calculate_priority_score(
        donation, good_capacity, now
    )

    low_score = calculate_priority_score(
        donation, low_capacity, now
    )

    assert good_score > low_score


def test_missing_coordinates():
    now = datetime.now()

    donation = make_donation(
        now,
        latitude=None,
        longitude=None
    )

    recipient = make_recipient()

    score = calculate_priority_score(
        donation, recipient, now
    )

    assert 0 <= score <= 100


def test_expire_old_donations():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret"
    })

    with app.app_context():
        db.create_all()

        now = datetime.now()

        provider = User(
            name="Test Provider",
            email="expiry@test.com",
            role="provider",
            is_verified=True
        )

        provider.set_password("password123")

        db.session.add(provider)
        db.session.commit()

        old_donation = Donation(
            provider_id=provider.id,
            food_name="Old Rice",
            quantity=50,
            unit="meals",
            expiry_time=now - timedelta(hours=2),
            status="available"
        )

        fresh_donation = Donation(
            provider_id=provider.id,
            food_name="Fresh Rice",
            quantity=100,
            unit="meals",
            expiry_time=now + timedelta(hours=5),
            status="available"
        )

        db.session.add_all([
            old_donation,
            fresh_donation
        ])

        db.session.commit()

        count = expire_old_donations(
            db.session,
            now
        )

        assert count == 1

        db.session.refresh(old_donation)
        db.session.refresh(fresh_donation)

        assert old_donation.status == "expired"
        assert fresh_donation.status == "available"

        db.session.remove()
        db.drop_all()
