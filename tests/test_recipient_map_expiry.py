"""Tests for the expiry badge and the map on the Find Food page (PR C)."""
import os
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Donation, User
from app.recipients.expiry import expiry_badge
from app.recipients.mapdata import map_markers, maps_api_key

FOOD_POS = (12.2958, 76.6394)
NOW = datetime(2026, 11, 19, 12, 0, 0)


# ---------------------------------------------------------------- setup

@pytest.fixture(autouse=True)
def no_maps_key(monkeypatch):
    """Start every test without a Maps key; tests that need one set it."""
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)


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


def make_donation(app, provider_id, name, pos=None,
                  expires_in=timedelta(hours=5, minutes=30)):
    """Create an available donation; pos is (latitude, longitude)."""
    lat, lng = pos if pos else (None, None)
    now = datetime.now()
    with app.app_context():
        donation = Donation(
            provider_id=provider_id, food_name=name, quantity=10,
            unit="kg", prepared_at=now - timedelta(hours=1),
            expiry_time=now + expires_in,
            pickup_location="Main Canteen", status="available",
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


def item(name, lat=None, lng=None):
    """A stand-in for one entry of the Find Food list (no database)."""
    donation = SimpleNamespace(
        food_name=name, quantity=10, unit="kg",
        latitude=lat, longitude=lng, pickup_location="Main Canteen",
    )
    provider = SimpleNamespace(name="College Canteen")
    return {"donation": donation, "provider": provider}


# ------------------------------------------------------- expiry badge

def test_badge_expired():
    badge = expiry_badge(NOW - timedelta(minutes=1), now=NOW)
    assert badge == {"text": "Expired", "css": "bg-secondary"}


def test_badge_exactly_now_is_expired():
    assert expiry_badge(NOW, now=NOW)["text"] == "Expired"


def test_badge_under_two_hours_is_expiring_soon():
    badge = expiry_badge(NOW + timedelta(hours=1, minutes=59), now=NOW)
    assert badge == {"text": "Expiring soon", "css": "bg-danger"}


def test_badge_two_hours_or_more_shows_whole_hours():
    two = expiry_badge(NOW + timedelta(hours=2), now=NOW)
    assert two == {"text": "Expires in 2h", "css": "bg-success"}
    three = expiry_badge(NOW + timedelta(hours=3, minutes=45), now=NOW)
    assert three["text"] == "Expires in 3h"


# ------------------------------------------------------ API key helper

def test_api_key_is_none_when_not_set():
    assert maps_api_key() is None


def test_api_key_blank_counts_as_not_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "   ")
    assert maps_api_key() is None


def test_api_key_is_read_and_trimmed(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "  abc123 ")
    assert maps_api_key() == "abc123"


# ------------------------------------------------------ marker builder

def test_markers_only_for_donations_with_coordinates():
    markers = map_markers([item("Rice", *FOOD_POS), item("Dal")])
    assert markers == [{
        "lat": 12.2958, "lng": 76.6394, "title": "Rice",
        "provider": "College Canteen", "quantity": "10 kg",
    }]


def test_markers_skip_out_of_range_coordinates():
    assert map_markers([item("Rice", 95.0, 76.6)]) == []


def test_no_items_gives_no_markers():
    assert map_markers([]) == []


# ------------------------------------------------------ Find Food page

def test_page_shows_expiry_badges(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice",
                  expires_in=timedelta(minutes=45))
    make_donation(app, provider, "LaterDal")
    page = get_page(app, ngo)
    assert "Expiring soon" in page
    assert "badge bg-danger ms-1" in page
    assert "Expires in 5h" in page
    assert "badge bg-success ms-1" in page


def test_page_without_key_shows_note_and_no_map(app):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice", pos=FOOD_POS)
    page = get_page(app, ngo)
    assert "SoonRice" in page          # the list still works
    assert "The map is not available right now" in page
    assert 'id="donation-map"' not in page
    assert "maps.googleapis.com" not in page


def test_page_with_key_and_coordinates_shows_map(app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice", pos=FOOD_POS)
    page = get_page(app, ngo)
    assert 'id="donation-map"' in page
    assert "maps.googleapis.com/maps/api/js?key=test-key" in page
    assert "callback=initDonationMap" in page
    assert '"lat"' in page
    assert "The map is not available right now" not in page


def test_page_with_key_but_no_coordinates_has_no_map(app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice")
    page = get_page(app, ngo)
    assert "SoonRice" in page
    assert "None of these donations has a map location yet" in page
    assert 'id="donation-map"' not in page
    assert "maps.googleapis.com" not in page


def test_page_only_marks_donations_that_have_coordinates(app, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "RiceOne", pos=FOOD_POS)
    make_donation(app, provider, "RiceTwo")
    page = get_page(app, ngo)
    assert page.count('"lat"') == 1    # one marker, both cards listed
    assert "RiceOne" in page and "RiceTwo" in page


# ---------------------------------------- expiry uses the system clock

@pytest.fixture()
def ist_clock():
    """Run with the system clock in IST (UTC+5:30), where local time and
    UTC differ by 5.5 hours. Providers save expiry times in local time."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is not available on Windows")
    old = os.environ.get("TZ")
    os.environ["TZ"] = "Asia/Kolkata"
    time.tzset()
    yield
    if old is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old
    time.tzset()


def test_expiry_badge_follows_system_time(app, ist_clock):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "SoonRice",
                  expires_in=timedelta(minutes=45))
    page = get_page(app, ngo)
    assert "SoonRice" in page
    assert "Expiring soon" in page      # not "Expires in 6h"


def test_food_past_expiry_in_system_time_is_hidden(app, ist_clock):
    provider = make_user(app, "Provider", "provider")
    ngo = make_user(app, "Ngo", "recipient")
    make_donation(app, provider, "OldRice", expires_in=timedelta(hours=-1))
    make_donation(app, provider, "FreshDal")
    page = get_page(app, ngo)
    assert "FreshDal" in page
    assert "OldRice" not in page
