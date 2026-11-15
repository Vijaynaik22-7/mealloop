
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.matching.priority import (
    calculate_priority_score,
    calculate_distance,
)


def make_donation(now, expiry_hours=10, quantity=100,
                  latitude=12.30, longitude=76.65):
    return SimpleNamespace(
        prepared_at=now - timedelta(hours=2),
        created_at=now - timedelta(hours=2),
        expiry_time=now + timedelta(hours=expiry_hours),
        quantity=quantity,
        latitude=latitude,
        longitude=longitude,
        status="available"
    )


def make_recipient(capacity=100, latitude=12.30,
                   longitude=76.65):
    return SimpleNamespace(
        capacity_people=capacity,
        latitude=latitude,
        longitude=longitude
    )


def test_distance_same_location():
    distance = calculate_distance(
        12.30, 76.65, 12.30, 76.65
    )

    assert distance == 0


def test_expired_donation_score_is_zero():
    now = datetime.utcnow()

    donation = make_donation(
        now,
        expiry_hours=-1
    )

    recipient = make_recipient()

    score = calculate_priority_score(
        donation, recipient, now
    )

    assert score == 0.0


def test_score_is_between_zero_and_hundred():
    now = datetime.utcnow()

    donation = make_donation(now)
    recipient = make_recipient()

    score = calculate_priority_score(
        donation, recipient, now
    )

    assert 0 <= score <= 100


def test_near_recipient_gets_higher_score():
    now = datetime.utcnow()

    donation = make_donation(now)

    near = make_recipient(
        latitude=12.30,
        longitude=76.65
    )

    far = make_recipient(
        latitude=13.00,
        longitude=77.00
    )

    near_score = calculate_priority_score(
        donation, near, now
    )

    far_score = calculate_priority_score(
        donation, far, now
    )

    assert near_score > far_score


def test_urgent_donation_gets_higher_score():
    now = datetime.utcnow()

    urgent = make_donation(
        now,
        expiry_hours=1
    )

    less_urgent = make_donation(
        now,
        expiry_hours=10
    )

    recipient = make_recipient()

    urgent_score = calculate_priority_score(
        urgent, recipient, now
    )

    less_urgent_score = calculate_priority_score(
        less_urgent, recipient, now
    )

    assert urgent_score > less_urgent_score


def test_better_capacity_fit_gets_higher_score():
    now = datetime.utcnow()

    donation = make_donation(now, quantity=100)

    good_fit = make_recipient(capacity=100)
    poor_fit = make_recipient(capacity=20)

    good_score = calculate_priority_score(
        donation, good_fit, now
    )

    poor_score = calculate_priority_score(
        donation, poor_fit, now
    )

    assert good_score > poor_score


def test_missing_coordinates():
    now = datetime.utcnow()

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
