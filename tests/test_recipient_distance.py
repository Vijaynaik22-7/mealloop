"""Tests for the distance shown on the NGO Find Food page (PR A)."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.matching.priority import calculate_distance
from app.models import Donation, User
from app.recipients.distance import (
    distance_km, distance_label, has_location,
)

# Hope Shelter and the Main Canteen from the demo seed (about 2 km apart)
NGO_POS = (12.3050, 76.6550)
FOOD_POS = (12.2958, 76.6394)


# ---------------------------------------------------------------- setup

@pytest.fixture()
def app():
    """A fresh app with an empty in-memory database for every test."""
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def make_user(app, name, role, pos=None, verified=True):
    """Create a user; pos is (latitude, longitude) or None."""
    lat, lng = pos if pos else (None, None)
    with app.app_context():
        user = User(
            name=name, email=f"{name.lower()}@test.com", role=role,
            password_hash=generate_password_hash("pass1234"),
            address="Somewhere", capacity_people=50,
            latitude=lat, longitude=lng, is_verified=verified,
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def make_donation(app, provider_id, name, pos=None):
    """Create an available donation; pos is (latitude, longitude)."""
    lat, lng = pos if pos else (None, None)
    now = datetime.now()
    with app.app_context():
        donation = Donation(
            provider_id=provider_id, food_name=name, quantity=10,
            unit="kg", prepared_at=now - timedelta(hours=1),
            expiry_time=now + timedelta(hours=3),
            pickup_location="Main Canteen", status="available",
            latitude=lat, longitude=lng,
        )
        db.session.add(donation)
        db.session.commit()
        return donation.id


def get_page(app, user_id, url="/recipient/donations"):
    """Open a page as an already logged-in user."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    response = client.get(url)
    assert response.status_code == 200
    return response.data.decode()


# ------------------------------------------------- helper functions

def test_has_location_needs_both_coordinates():
    assert has_location(SimpleNamespace(latitude=1.0, longitude=2.0))
    assert not has_location(SimpleNamespace(latitude=1.0, longitude=None))
    assert not has_location(SimpleNamespace(latitude=None, longitude=2.0))


def test_distance_km_matches_demo_seed_places():
    ngo = SimpleNamespace(latitude=NGO_POS[0], longitude=NGO_POS[1])
    food = SimpleNamespace(latitude=FOOD_POS[0], longitude=FOOD_POS[1])
    assert 1.9 < distance_km(ngo, food) < 2.1


def test_distance_km_is_none_when_a_coordinate_is_missing():
    ngo = SimpleNamespace(latitude=12.3, longitude=76.6)
    no_food = SimpleNamespace(latitude=None, longitude=None)
    assert distance_km(ngo, no_food) is None
    assert distance_km(no_food, ngo) is None


def test_distance_km_is_none_for_unusable_data():
    ngo = SimpleNamespace(latitude=12.3, longitude=76.6)
    bad = SimpleNamespace(latitude="abc", longitude=76.6)
    assert distance_km(ngo, bad) is None


def test_distance_label_text():
    assert distance_label(2.04) == "about 2.0 km (straight line)"
    assert distance_label(None) == "distance unknown"


# ------------------------------------------------------ Find Food page

def test_page_shows_distance_when_both_have_coordinates(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient", pos=NGO_POS)
    make_donation(app, provider, "SoonRice", pos=FOOD_POS)
    expected = distance_label(calculate_distance(*NGO_POS, *FOOD_POS))
    page = get_page(app, ngo)
    assert expected in page
    assert "about 2.0 km (straight line)" in page
    # The NGO has a location, so no "add your location" notice
    assert "Add your location" not in page


def test_page_says_unknown_when_donation_has_no_coordinates(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient", pos=NGO_POS)
    make_donation(app, provider, "SoonRice")
    page = get_page(app, ngo)
    assert "SoonRice" in page
    assert "distance unknown" in page


def test_ngo_without_location_sees_profile_link(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice", pos=FOOD_POS)
    page = get_page(app, ngo)
    assert "SoonRice" in page          # the page still works
    assert "distance unknown" in page
    assert "Add your location" in page
    assert 'href="/recipient/profile"' in page


def test_unverified_ngo_page_still_works(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Newbie", "recipient", verified=False)
    make_donation(app, provider, "SoonRice", pos=FOOD_POS)
    page = get_page(app, ngo)
    assert "pending approval" in page
    assert "SoonRice" not in page
