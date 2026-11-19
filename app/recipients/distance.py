"""Distance helpers for the Find Food page (Member 2).

The NGO's position comes from current_user, the food's position from
the Donation. If either one is missing we say "distance unknown"
instead of crashing.
"""
from app.matching.priority import calculate_distance


def has_location(thing):
    """True if a User or Donation has both latitude and longitude."""
    return thing.latitude is not None and thing.longitude is not None


def distance_km(recipient, donation):
    """Straight-line distance in km from the NGO to the donation.

    Returns None when a coordinate is missing or cannot be used.
    """
    if not has_location(recipient) or not has_location(donation):
        return None
    try:
        return calculate_distance(
            recipient.latitude, recipient.longitude,
            donation.latitude, donation.longitude,
        )
    except (TypeError, ValueError):
        # Bad data in the database must never break the page
        return None


def distance_label(km):
    """Text shown on the donation card."""
    if km is None:
        return "distance unknown"
    return f"about {km:.1f} km (straight line)"
