"""Distance helpers for the Find Food page (Member 2).

The NGO's position comes from current_user, the food's position from
the Donation. If either one is missing we say "distance unknown"
instead of crashing.

Road distance (optional extra): one call to the free public OSRM server
gives the driving distance to every donation at once. If anything goes
wrong (no internet, timeout, bad answer) we silently use the
straight-line distance instead. Uses only the standard library.
"""
import json
import os
import time
import urllib.request

from flask import current_app

from app.matching.priority import calculate_distance

OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"
OSRM_TIMEOUT_SECONDS = 3    # never make the page wait longer than this
OSRM_PAUSE_SECONDS = 60     # after a failure, do not try again for a minute
MAX_ROAD_DESTINATIONS = 25  # donations beyond this use straight-line

# time.monotonic() value before which we do not call OSRM again
_skip_until = 0.0


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


def distance_label(km, by_road=False):
    """Text shown on the donation card."""
    if km is None:
        return "distance unknown"
    if by_road:
        return f"about {km:.1f} km by road"
    return f"about {km:.1f} km (straight line)"


def road_distance_enabled():
    """Should the app try to fetch road distances?

    Off in tests (no internet in unit tests). For a demo without internet
    set the environment variable ROAD_DISTANCE=off. A config value
    ROAD_DISTANCE_ENABLED overrides both (used by our own tests).
    """
    if "ROAD_DISTANCE_ENABLED" in current_app.config:
        return bool(current_app.config["ROAD_DISTANCE_ENABLED"])
    if current_app.config.get("TESTING", False):
        return False
    return os.environ.get("ROAD_DISTANCE", "on").strip().lower() != "off"


def road_distances_km(recipient, donations):
    """Driving distance in km from the NGO to each donation.

    Returns a dict {donation_id: km}. Returns {} when the NGO has no
    location, no donation has one, OSRM was recently down, or anything
    goes wrong. Donations missing from the dict use straight-line.
    """
    global _skip_until

    if not has_location(recipient):
        return {}
    located = [d for d in donations if has_location(d)]
    located = located[:MAX_ROAD_DESTINATIONS]
    if not located:
        return {}
    if time.monotonic() < _skip_until:
        return {}

    # OSRM wants longitude,latitude (not latitude,longitude!)
    points = [recipient] + located
    coords = ";".join(f"{p.longitude},{p.latitude}" for p in points)
    url = f"{OSRM_TABLE_URL}{coords}?sources=0&annotations=distance"
    http_request = urllib.request.Request(
        url, headers={"User-Agent": "MealLoop-college-project"})

    try:
        with urllib.request.urlopen(
                http_request, timeout=OSRM_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("code") != "Ok":
            raise ValueError("OSRM did not answer Ok")
        # One row (source 0): metres to the NGO itself, then to each donation
        row = data["distances"][0]
        if len(row) != len(located) + 1:
            raise ValueError("OSRM answer has the wrong size")
        result = {}
        for donation, metres in zip(located, row[1:]):
            if metres is not None:
                result[donation.id] = metres / 1000
        return result
    except (OSError, ValueError, KeyError, IndexError, TypeError,
            AttributeError):
        # No internet, timeout, bad JSON... use straight-line for a while
        _skip_until = time.monotonic() + OSRM_PAUSE_SECONDS
        return {}


def best_distance_label(recipient, donation, road_km=None):
    """Road distance text if we have it, otherwise straight-line text."""
    if road_km is not None:
        return distance_label(road_km, by_road=True)
    return distance_label(distance_km(recipient, donation))
