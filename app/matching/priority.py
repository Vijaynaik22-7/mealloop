"""Priority scoring and automatic donation expiry."""

from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

from app.models import Donation, DonationRequest


URGENCY_WEIGHT = 0.50
DISTANCE_WEIGHT = 0.30
CAPACITY_WEIGHT = 0.20

MAX_DISTANCE_KM = 50


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two locations."""

    earth_radius = 6371

    lat1, lon1, lat2, lon2 = map(
        radians, (lat1, lon1, lat2, lon2)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c


def calculate_priority_score(donation, recipient, now=None):
    """Calculate donation priority score between 0 and 100."""

    if now is None:
        now = datetime.utcnow()

    if donation.expiry_time <= now:
        return 0.0

    prepared_at = donation.prepared_at or donation.created_at or now

    total_time = (
        donation.expiry_time - prepared_at
    ).total_seconds()

    remaining_time = (
        donation.expiry_time - now
    ).total_seconds()

    if total_time <= 0:
        urgency_score = 0
    else:
        urgency_score = max(
            0,
            min(100, 100 * (1 - remaining_time / total_time))
        )

    coordinates = (
        donation.latitude,
        donation.longitude,
        recipient.latitude,
        recipient.longitude
    )

    if any(value is None for value in coordinates):
        distance_score = 0
    else:
        distance = calculate_distance(*coordinates)

        distance_score = max(
            0,
            min(100, 100 * (1 - distance / MAX_DISTANCE_KM))
        )

    if donation.quantity <= 0 or not recipient.capacity_people:
        capacity_score = 0
    else:
        capacity_score = min(
            100,
            (recipient.capacity_people / donation.quantity) * 100
        )

    final_score = (
        urgency_score * URGENCY_WEIGHT
        + distance_score * DISTANCE_WEIGHT
        + capacity_score * CAPACITY_WEIGHT
    )

    return round(final_score, 2)


def expire_old_donations(db_session, now=None):
    """Expire donations whose expiry time has passed.

    Both "available" and "requested" donations expire. When a requested
    donation expires, its pending requests are rejected so the NGO does
    not wait for food that is no longer safe. Accepted donations are left
    alone (the NGO is already collecting them).

    Returns the number of donations that were expired.
    """

    if now is None:
        now = datetime.utcnow()

    expired_ids = [
        row.id
        for row in db_session.query(Donation.id).filter(
            Donation.status.in_(("available", "requested")),
            Donation.expiry_time <= now,
        )
    ]

    if not expired_ids:
        return 0

    # Reject the pending requests first, then expire the donations.
    db_session.query(DonationRequest).filter(
        DonationRequest.donation_id.in_(expired_ids),
        DonationRequest.status == "pending",
    ).update({"status": "rejected"}, synchronize_session=False)

    expired_count = (
        db_session.query(Donation)
        .filter(Donation.id.in_(expired_ids))
        .update({"status": "expired"}, synchronize_session=False)
    )

    db_session.commit()

    return expired_count
