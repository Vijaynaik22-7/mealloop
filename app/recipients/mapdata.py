"""Data for the Google Maps map on the Find Food page (Member 2).

The map is an extra. If there is no API key, or no donation has
coordinates, the page simply shows no map.
"""
import os

# Same coordinate check the directions link uses (same module folder)
from app.recipients.directions import _valid_coordinates


def maps_api_key():
    """The Google Maps key from the environment, or None if not set.

    The key is never stored in code, tests or the repo.
    """
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    return key or None


def map_markers(items):
    """One marker per donation that has usable coordinates.

    `items` is the list built by the Find Food route (dicts with
    "donation" and "provider"). Donations without coordinates are
    skipped, they still show in the list below the map.
    """
    markers = []
    for item in items:
        donation = item["donation"]
        coordinates = _valid_coordinates(donation)
        if coordinates is None:
            continue
        markers.append({
            "lat": coordinates[0],
            "lng": coordinates[1],
            "title": donation.food_name,
            "provider": item["provider"].name,
            "quantity": f"{donation.quantity} {donation.unit}",
        })
    return markers
