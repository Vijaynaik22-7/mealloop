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
