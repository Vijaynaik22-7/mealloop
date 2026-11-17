"""Tests for the auth module: register, login, logout, role_required."""
import pytest

from app import create_app
from app.auth.utils import role_required, verified_required
from app.extensions import db
from app.models import User


# ------------------------------------------------------------------
# Fixtures: pieces every test can reuse
# ------------------------------------------------------------------
@pytest.fixture()
def app():
    """A fresh app with an empty in-memory database for each test."""
    flask_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret",
    })

    # Two test-only pages, used to check role_required / verified_required
    @flask_app.route("/_test/provider-only")
    @role_required("provider")
    def provider_only():
        return "provider area"

    @flask_app.route("/_test/verified-only")
    @role_required("recipient")
    @verified_required
    def verified_only():
        return "verified area"

    yield flask_app

    # Clean up the database after the test
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """A fake browser that can send requests to the app."""
    return app.test_client()


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def make_user(app, email="user@example.com", password="secret123",
              role="provider", verified=True, **extra):
    """Put a user straight into the database."""
    with app.app_context():
        user = User(name="Test " + role, email=email, role=role,
                    is_verified=verified, **extra)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def get_user(app, email):
    """Fetch a user (or None) by email."""
    with app.app_context():
        return User.query.filter_by(email=email).first()


def register_data(**overrides):
    """Valid form data for registering; override fields per test."""
    data = {
        "name": "Green Canteen",
        "email": "canteen@example.com",
        "password": "secret123",
        "confirm_password": "secret123",
        "role": "provider",
        "phone": "9999999999",
        "address": "Mysuru",
    }
    data.update(overrides)
    return data


def login(client, email, password):
    return client.post("/auth/login",
                       data={"email": email, "password": password})


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
def test_register_provider_is_auto_verified(client, app):
    response = client.post("/auth/register", data=register_data())

    assert response.status_code == 302            # redirected to login
    assert response.headers["Location"].endswith("/auth/login")
    user = get_user(app, "canteen@example.com")
    assert user is not None
    assert user.role == "provider"
    assert user.is_verified is True


def test_register_recipient_starts_unverified(client, app):
    data = register_data(email="ngo@example.com", role="recipient",
                         capacity_people="50")
    response = client.post("/auth/register", data=data)

    assert response.status_code == 302
    user = get_user(app, "ngo@example.com")
    assert user.role == "recipient"
    assert user.is_verified is False              # waits for admin
    assert user.capacity_people == 50


def test_recipient_needs_capacity(client, app):
    data = register_data(email="ngo@example.com", role="recipient")
    response = client.post("/auth/register", data=data)

    assert response.status_code == 200            # form shown again
    assert get_user(app, "ngo@example.com") is None


def test_cannot_register_as_admin(client, app):
    data = register_data(email="hacker@example.com", role="admin")
    response = client.post("/auth/register", data=data)

    assert response.status_code == 200
    assert get_user(app, "hacker@example.com") is None


def test_duplicate_email_rejected(client, app):
    make_user(app, email="canteen@example.com")
    response = client.post("/auth/register", data=register_data())

    assert response.status_code == 200
    assert b"already registered" in response.data


def test_passwords_must_match(client, app):
    data = register_data(confirm_password="different")
    response = client.post("/auth/register", data=data)

    assert response.status_code == 200
    assert get_user(app, "canteen@example.com") is None


def test_password_is_hashed(client, app):
    client.post("/auth/register", data=register_data())

    user = get_user(app, "canteen@example.com")
    assert user.password_hash != "secret123"      # never plain text
    assert user.check_password("secret123") is True


# ------------------------------------------------------------------
# Login and logout
# ------------------------------------------------------------------
@pytest.mark.parametrize("role, dashboard", [
    ("provider", "/provider/dashboard"),
    ("recipient", "/recipient/dashboard"),
    ("admin", "/admin/dashboard"),
])
def test_login_redirects_to_role_dashboard(client, app, role, dashboard):
    make_user(app, email="u@example.com", role=role)
    response = login(client, "u@example.com", "secret123")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(dashboard)


def test_login_wrong_password(client, app):
    make_user(app)
    response = login(client, "user@example.com", "wrong-password")

    assert response.status_code == 200            # stays on login page
    assert b"Invalid email or password" in response.data
    # ...and we are NOT logged in
    protected = client.get("/_test/provider-only")
    assert protected.status_code == 302


def test_login_unknown_email(client):
    response = login(client, "nobody@example.com", "secret123")

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_logout(client, app):
    make_user(app)
    login(client, "user@example.com", "secret123")
    assert client.get("/_test/provider-only").status_code == 200

    response = client.get("/auth/logout")
    assert response.status_code == 302

    after = client.get("/_test/provider-only")    # logged out now
    assert after.status_code == 302
    assert "/auth/login" in after.headers["Location"]


# ------------------------------------------------------------------
# role_required / verified_required
# ------------------------------------------------------------------
def test_role_required_sends_anonymous_to_login(client):
    response = client.get("/_test/provider-only")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_role_required_allows_correct_role(client, app):
    make_user(app, role="provider")
    login(client, "user@example.com", "secret123")

    response = client.get("/_test/provider-only")
    assert response.status_code == 200
    assert b"provider area" in response.data


def test_role_required_blocks_other_roles(client, app):
    make_user(app, email="ngo@example.com", role="recipient")
    login(client, "ngo@example.com", "secret123")

    response = client.get("/_test/provider-only")
    # Sent back to their OWN dashboard, never shown the provider page
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/recipient/dashboard")


def test_admin_is_also_blocked_from_provider_page(client, app):
    make_user(app, email="admin@example.com", role="admin")
    login(client, "admin@example.com", "secret123")

    response = client.get("/_test/provider-only")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/dashboard")


def test_verified_required_blocks_unverified_recipient(client, app):
    make_user(app, email="ngo@example.com", role="recipient",
              verified=False)
    login(client, "ngo@example.com", "secret123")

    response = client.get("/_test/verified-only")
    assert response.status_code == 302            # blocked


def test_verified_required_allows_verified_recipient(client, app):
    make_user(app, email="ngo@example.com", role="recipient",
              verified=True)
    login(client, "ngo@example.com", "secret123")

    response = client.get("/_test/verified-only")
    assert response.status_code == 200
    assert b"verified area" in response.data
