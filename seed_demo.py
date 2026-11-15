
"""Create sample MealLoop data for project demonstration."""

from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import User, Donation, DonationRequest


app = create_app()

with app.app_context():

    provider = User.query.filter_by(
        email="demo_provider@mealloop.com"
    ).first()

    if provider is None:
        provider = User(
            name="Demo Restaurant",
            email="demo_provider@mealloop.com",
            role="provider",
            address="Mysuru",
            latitude=12.2958,
            longitude=76.6394,
            is_verified=True
        )
        provider.set_password("Demo123")

        db.session.add(provider)

    recipient = User.query.filter_by(
        email="demo_ngo@mealloop.com"
    ).first()

    if recipient is None:
        recipient = User(
            name="Demo NGO",
            email="demo_ngo@mealloop.com",
            role="recipient",
            address="Mysuru",
            latitude=12.3000,
            longitude=76.6500,
            capacity_people=150,
            is_verified=True
        )
        recipient.set_password("Demo123")

        db.session.add(recipient)

    db.session.commit()

    if Donation.query.filter_by(
        food_name="Demo Rice"
    ).first() is None:

        donation1 = Donation(
            provider_id=provider.id,
            food_name="Demo Rice",
            quantity=100,
            unit="meals",
            prepared_at=datetime.utcnow() - timedelta(hours=2),
            expiry_time=datetime.utcnow() + timedelta(hours=5),
            pickup_location="Mysuru",
            latitude=12.2958,
            longitude=76.6394,
            status="collected"
        )

        donation2 = Donation(
            provider_id=provider.id,
            food_name="Demo Vegetables",
            quantity=50,
            unit="meals",
            prepared_at=datetime.utcnow(),
            expiry_time=datetime.utcnow() + timedelta(hours=8),
            pickup_location="Mysuru",
            latitude=12.2958,
            longitude=76.6394,
            status="available"
        )

        donation3 = Donation(
            provider_id=provider.id,
            food_name="Demo Chapati",
            quantity=40,
            unit="meals",
            prepared_at=datetime.utcnow() - timedelta(hours=1),
            expiry_time=datetime.utcnow() + timedelta(hours=4),
            pickup_location="Mysuru",
            latitude=12.2958,
            longitude=76.6394,
            status="collected"
        )

        db.session.add_all([
            donation1,
            donation2,
            donation3
        ])

        db.session.commit()

        request = DonationRequest(
            donation_id=donation1.id,
            recipient_id=recipient.id,
            people_to_serve=100,
            status="collected",
            priority_score=85.0,
            collected_at=datetime.utcnow()
        )

        db.session.add(request)
        db.session.commit()

    print("MealLoop demo data created successfully.")
    print("Provider: demo_provider@mealloop.com")
    print("NGO: demo_ngo@mealloop.com")
    print("Demo password: Demo123")
