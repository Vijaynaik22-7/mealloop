from app import create_app
from app.models import Donation, DonationRequest, User
from seed import seed_demo_data


def make_app():
    # In-memory database so the real one is never touched
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})


def test_seed_creates_demo_data():
    app = make_app()
    with app.app_context():
        assert seed_demo_data() is True
        assert User.query.filter_by(role="admin").count() == 1
        assert User.query.filter_by(role="recipient", is_verified=True).count() == 1
        assert User.query.filter_by(role="recipient", is_verified=False).count() == 1
        assert Donation.query.count() == 5
        assert Donation.query.filter_by(status="available").count() == 4
        assert DonationRequest.query.filter_by(status="collected").count() == 1


def test_seed_is_safe_to_run_twice():
    app = make_app()
    with app.app_context():
        seed_demo_data()
        assert seed_demo_data() is False  # second run does nothing
        assert User.query.count() == 4
        assert Donation.query.count() == 5


def test_seed_phones_have_country_code(monkeypatch):
    # No overrides set: the defaults must start with 91 for WhatsApp
    monkeypatch.delenv("DEMO_PROVIDER_PHONE", raising=False)
    monkeypatch.delenv("DEMO_NGO_PHONE", raising=False)
    monkeypatch.delenv("DEMO_NGO2_PHONE", raising=False)
    app = make_app()
    with app.app_context():
        seed_demo_data()
        for user in User.query.filter(User.role != "admin"):
            assert user.phone.startswith("91")


def test_seed_phone_can_be_overridden(monkeypatch):
    monkeypatch.setenv("DEMO_NGO_PHONE", "911234567890")
    app = make_app()
    with app.app_context():
        seed_demo_data()
        ngo = User.query.filter_by(email="hope@mealloop.com").first()
        assert ngo.phone == "911234567890"
