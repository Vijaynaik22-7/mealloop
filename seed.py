"""Create demo data (admin, provider, NGOs, donations) on an EMPTY database.

Run locally:   python seed.py
In Docker:     runs automatically before gunicorn starts (see Dockerfile).
Safe to run twice: if any user already exists, it does nothing.

Phone numbers use the country code (91) so WhatsApp links and the WhatsApp
API work. To use real test numbers, set these environment variables
(for example on Render) before the first start:
  DEMO_PROVIDER_PHONE, DEMO_NGO_PHONE, DEMO_NGO2_PHONE
"""
import os
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import Donation, DonationRequest, User

# Demo logins (shown to the examiner, never use these in real life)
DEMO_PASSWORD = "Demo@1234"


def make_user(name, email, role, verified, **extra):
    """Build a User with a hashed password."""
    user = User(name=name, email=email, role=role, is_verified=verified, **extra)
    user.set_password(DEMO_PASSWORD)
    return user


def seed_demo_data():
    """Add demo rows. Must be called inside an app context."""
    if User.query.first() is not None:
        print("Seed skipped: database already has users.")
        return False

    # Read at call time so tests and Render can override them
    provider_phone = os.environ.get("DEMO_PROVIDER_PHONE", "919800000001")
    ngo_phone = os.environ.get("DEMO_NGO_PHONE", "919800000002")
    ngo2_phone = os.environ.get("DEMO_NGO2_PHONE", "919800000003")

    admin = make_user("MealLoop Admin", "admin@mealloop.com", "admin", True)

    canteen = make_user(
        "College Canteen", "canteen@mealloop.com", "provider", True,
        phone=provider_phone, address="Main Canteen, Mysuru",
        latitude=12.2958, longitude=76.6394,
    )
    ngo_ok = make_user(
        "Hope Foundation", "hope@mealloop.com", "recipient", True,
        phone=ngo_phone, address="Hope Shelter, Mysuru",
        latitude=12.3050, longitude=76.6550, capacity_people=80,
    )
    ngo_pending = make_user(
        "New Helpers Trust", "helpers@mealloop.com", "recipient", False,
        phone=ngo2_phone, address="Gokulam, Mysuru",
        latitude=12.3200, longitude=76.6300, capacity_people=40,
    )
    db.session.add_all([admin, canteen, ngo_ok, ngo_pending])
    db.session.commit()  # commit first so the ids exist

    now = datetime.utcnow()
    donations = [
        # (food, quantity, unit, hours until expiry)
        ("Vegetable biryani", 40, "plates", 3),
        ("Chapati and dal", 60, "plates", 6),
        ("Fresh bread", 25, "packets", 12),
        ("Fruit salad", 15, "boxes", 2),
    ]
    for food, qty, unit, hours in donations:
        db.session.add(Donation(
            provider_id=canteen.id,
            food_name=food,
            quantity=qty,
            unit=unit,
            prepared_at=now,
            expiry_time=now + timedelta(hours=hours),
            pickup_location="Main Canteen, Mysuru",
            latitude=12.2958,
            longitude=76.6394,
            status="available",
        ))

    # One finished rescue, so the Impact page shows real numbers
    done = Donation(
        provider_id=canteen.id,
        food_name="Rice and sambar",
        quantity=50,
        unit="plates",
        prepared_at=now - timedelta(hours=5),
        expiry_time=now + timedelta(hours=1),
        pickup_location="Main Canteen, Mysuru",
        latitude=12.2958,
        longitude=76.6394,
        status="collected",
    )
    db.session.add(done)
    db.session.commit()

    db.session.add(DonationRequest(
        donation_id=done.id,
        recipient_id=ngo_ok.id,
        people_to_serve=50,
        status="collected",
        priority_score=82.5,
        collected_at=now - timedelta(hours=1),
    ))
    db.session.commit()

    print("Seeded: 1 admin, 1 provider, 2 NGOs (1 verified), "
          "5 donations (1 collected).")
    return True


if __name__ == "__main__":
    app = create_app()  # create_app also creates the tables
    with app.app_context():
        seed_demo_data()
