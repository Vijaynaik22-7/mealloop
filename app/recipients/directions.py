"""Google Maps directions link for a donation (Member 2).

No API key is needed: this is a plain link that opens Google Maps.
"""
from urllib.parse import urlencode

from app.recipients.distance import has_location

DIRECTIONS_URL = "https://www.google.com/maps/dir/"


def _valid_coordinates(donation):
    """Return (latitude, longitude) if the donation has usable ones."""
    if not has_location(donation):
        return None
    try:
        lat = float(donation.latitude)
        lng = float(donation.longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def directions_url(donation):
    """Link that opens driving directions to the donation.

    Uses the coordinates when the donation has them, otherwise the
    pickup location text. Returns None if there is neither, so the
    page can hide the button instead of showing a broken link.
    """
    coordinates = _valid_coordinates(donation)
    if coordinates:
        destination = f"{coordinates[0]},{coordinates[1]}"
    else:
        destination = (donation.pickup_location or "").strip()
    if not destination:
        return None
    query = urlencode(
        {"api": "1", "destination": destination, "travelmode": "driving"},
        safe=",",  # keep the comma between latitude and longitude
    )
    return f"{DIRECTIONS_URL}?{query}"
