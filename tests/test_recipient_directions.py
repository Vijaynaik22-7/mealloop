"""Tests for the Get Directions button on the Find Food page (PR B)."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Donation, User
from app.recipients.directions import directions_url

FOOD_POS = (12.2958, 76.6394)
# What the link must look like for FOOD_POS (inside HTML, & becomes &amp;)
COORD_LINK = "destination=12.2958,76.6394&travelmode=driving"
COORD_LINK_HTML = "destination=12.2958,76.6394&amp;travelmode=driving"


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


def make_user(app, name, role):
    with app.app_context():
        user = User(
            name=name, email=f"{name.lower()}@test.com", role=role,
            password_hash=generate_password_hash("pass1234"),
            address="Somewhere", capacity_people=50, is_verified=True,
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def make_donation(app, provider_id, name, pos=None, pickup="Main Canteen"):
    """Create an available donation; pos is (latitude, longitude)."""
    lat, lng = pos if pos else (None, None)
    now = datetime.now()
    with app.app_context():
        donation = Donation(
            provider_id=provider_id, food_name=name, quantity=10,
            unit="kg", prepared_at=now - timedelta(hours=1),
            expiry_time=now + timedelta(hours=3),
            pickup_location=pickup, status="available",
            latitude=lat, longitude=lng,
        )
        db.session.add(donation)
        db.session.commit()
        return donation.id


def get_page(app, user_id):
    """Open Find Food as an already logged-in user."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    response = client.get("/recipient/donations")
    assert response.status_code == 200
    return response.data.decode()


def donation_like(lat=None, lng=None, pickup=None):
    """A simple stand-in for a Donation (no database needed)."""
    return SimpleNamespace(latitude=lat, longitude=lng,
                           pickup_location=pickup)


# ------------------------------------------------- helper function

def test_link_uses_coordinates_when_available():
    url = directions_url(donation_like(*FOOD_POS, pickup="Main Canteen"))
    assert url == (
        "https://www.google.com/maps/dir/?api=1&"
        "destination=12.2958,76.6394&travelmode=driving"
    )


def test_link_falls_back_to_pickup_text():
    url = directions_url(donation_like(pickup="Main Canteen, Mysuru"))
    assert url.startswith("https://www.google.com/maps/dir/?api=1&")
    assert "destination=Main+Canteen,+Mysuru" in url
    assert url.endswith("&travelmode=driving")


def test_link_encodes_special_characters_in_pickup_text():
    url = directions_url(donation_like(pickup="Gate & Hall"))
    assert "destination=Gate+%26+Hall" in url


def test_link_is_none_without_any_destination():
    assert directions_url(donation_like()) is None
    assert directions_url(donation_like(pickup="   ")) is None


def test_bad_coordinates_fall_back_to_pickup_text():
    out_of_range = donation_like(95.0, 76.6, pickup="Gate")
    not_a_number = donation_like("abc", 76.6, pickup="Gate")
    assert "destination=Gate&" in directions_url(out_of_range)
    assert "destination=Gate&" in directions_url(not_a_number)
    assert directions_url(donation_like(95.0, 76.6)) is None


# ------------------------------------------------------ Find Food page

def test_button_links_to_coordinates(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice", pos=FOOD_POS)
    page = get_page(app, ngo)
    assert "Get Directions" in page
    assert "https://www.google.com/maps/dir/?api=1&amp;" in page
    assert COORD_LINK_HTML in page


def test_button_uses_pickup_text_when_no_coordinates(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice", pickup="Main Canteen")
    page = get_page(app, ngo)
    assert "Get Directions" in page
    assert "destination=Main+Canteen&amp;travelmode=driving" in page


def test_button_hidden_when_no_destination_at_all(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice", pickup=None)
    page = get_page(app, ngo)
    assert "SoonRice" in page          # the page still works
    assert "Get Directions" not in page


def test_each_card_gets_its_own_link(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "RiceOne", pos=FOOD_POS)
    make_donation(app, provider, "RiceTwo", pickup="North Gate")
    page = get_page(app, ngo)
    assert page.count("Get Directions") == 2
    assert COORD_LINK_HTML in page
    assert "destination=North+Gate&amp;" in page
