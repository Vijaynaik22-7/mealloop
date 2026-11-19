"""Tests for the email OTP feature: helper functions, Brevo call, routes.

No real network is used anywhere: the Brevo HTTP call is replaced by fakes.
Environment variables are cleared before every test, so the results do not
depend on what is set on your computer.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytest
from werkzeug.security import check_password_hash

from app import create_app
from app.auth import otp
from app.auth.utils import role_required
from app.extensions import db
from app.models import EmailOtp, User

EMAIL = "canteen@example.com"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Every test starts with OTP off and no Brevo settings."""
    for name in ("OTP_ENABLED", "BREVO_API_KEY", "OTP_FROM_EMAIL",
                 "OTP_FROM_NAME"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def app():
    """A fresh app with an empty in-memory database for each test."""
    flask_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret",
    })

    # Test-only page: tells us whether someone is really logged in
    @flask_app.route("/_test/provider-only")
    @role_required("provider")
    def provider_only():
        return "provider area"

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def otp_on(monkeypatch):
    """Turn the OTP feature on."""
    monkeypatch.setenv("OTP_ENABLED", "true")


@pytest.fixture()
def sent(monkeypatch):
    """Replace the email sender; every (email, code) is saved in a list."""
    messages = []

    def fake_send(to_email, to_name, code):
        messages.append((to_email, code))
        return True

    monkeypatch.setattr("app.auth.routes.send_otp_email", fake_send)
    return messages


@pytest.fixture()
def brevo_env(monkeypatch):
    """Pretend the Brevo settings exist (fake values, not real keys)."""
    monkeypatch.setenv("BREVO_API_KEY", "test-key-123")
    monkeypatch.setenv("OTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("OTP_FROM_NAME", "MealLoop Test")


class FakeResponse:
    """Stands in for the object urllib.request.urlopen returns."""

    def __init__(self, status=201):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def new_user(email="otp@example.com"):
    """A user for the helper tests (call inside an app context)."""
    user = User(name="Otp User", email=email, role="provider",
                password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user


def make_user(app, email="user@example.com", password="secret123",
              role="provider", **extra):
    """Put a fully set up user straight into the database."""
    with app.app_context():
        user = User(name="Test " + role, email=email, role=role,
                    is_verified=True, **extra)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()


def user_value(app, email, field):
    with app.app_context():
        return getattr(User.query.filter_by(email=email).first(), field)


def age_last_sent(app, email, seconds):
    """Pretend the code was sent `seconds` earlier (to skip the wait)."""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        user.email_otp.last_sent_at -= timedelta(seconds=seconds)
        db.session.commit()


def register_data(**overrides):
    data = {
        "name": "Green Canteen",
        "email": EMAIL,
        "password": "secret123",
        "confirm_password": "secret123",
        "role": "provider",
        "phone": "9999999999",
        "address": "Mysuru",
    }
    data.update(overrides)
    return data


def register(client, **overrides):
    return client.post("/auth/register", data=register_data(**overrides))


def login(client, email, password="secret123"):
    return client.post("/auth/login",
                       data={"email": email, "password": password})


def wrong_code_for(code):
    """Any 6-digit code that is not `code`."""
    return "000000" if code != "000000" else "111111"


# ------------------------------------------------------------------
# Helper module: switch, code, hashing
# ------------------------------------------------------------------
def test_otp_is_off_by_default():
    assert otp.otp_enabled() is False


@pytest.mark.parametrize("value, expected", [
    ("true", True), ("TRUE", True), (" True ", True),
    ("false", False), ("yes", False), ("1", False), ("", False),
])
def test_otp_enabled_only_for_true(monkeypatch, value, expected):
    monkeypatch.setenv("OTP_ENABLED", value)
    assert otp.otp_enabled() is expected


def test_generated_code_has_six_digits():
    for _ in range(50):
        code = otp.generate_code()
        assert len(code) == 6
        assert code.isdigit()


def test_issue_otp_stores_hash_not_the_code(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)

        record = user.email_otp
        assert record.code_hash != code
        assert check_password_hash(record.code_hash, code)
        assert record.attempts == 0
        lifetime = record.expires_at - record.last_sent_at
        assert lifetime == timedelta(minutes=10)


def test_issue_otp_keeps_one_row_per_user(app):
    with app.app_context():
        user = new_user()
        otp.issue_otp(user)
        otp.issue_otp(user)
        assert EmailOtp.query.count() == 1


# ------------------------------------------------------------------
# Helper module: checking a typed code
# ------------------------------------------------------------------
def test_correct_code_verifies_the_user(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)

        assert otp.verify_otp(user, code) == (True, "ok")
        assert user.email_verified is True
        assert EmailOtp.query.count() == 0       # code is used up


def test_code_cannot_be_used_twice(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)
        otp.verify_otp(user, code)

        assert otp.verify_otp(user, code) == (False, "no_code")


def test_wrong_code_counts_attempts(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)

        assert otp.verify_otp(user, wrong_code_for(code)) == (False, "wrong")
        assert otp.attempts_left(user) == otp.MAX_ATTEMPTS - 1
        assert user.email_verified is False


def test_five_wrong_codes_lock_even_the_right_code(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)
        bad = wrong_code_for(code)

        reasons = [otp.verify_otp(user, bad)[1] for _ in range(5)]
        assert reasons == ["wrong"] * 4 + ["locked"]

        assert otp.verify_otp(user, code) == (False, "locked")
        assert user.email_verified is False


def test_new_code_resets_the_attempts(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)
        for _ in range(5):
            otp.verify_otp(user, wrong_code_for(code))

        new_code = otp.issue_otp(user)
        assert otp.attempts_left(user) == otp.MAX_ATTEMPTS
        assert otp.verify_otp(user, new_code) == (True, "ok")


def test_expired_code_is_rejected(app):
    with app.app_context():
        user = new_user()
        code = otp.issue_otp(user)
        later = datetime.utcnow() + timedelta(minutes=11)

        assert otp.verify_otp(user, code, now=later) == (False, "expired")
        assert user.email_verified is False


def test_badly_typed_code_does_not_use_an_attempt(app):
    with app.app_context():
        user = new_user()
        otp.issue_otp(user)

        for typed in ("12ab", "123", "1234567", "", None):
            assert otp.verify_otp(user, typed) == (False, "format")
        assert otp.attempts_left(user) == otp.MAX_ATTEMPTS


def test_verify_without_a_code(app):
    with app.app_context():
        user = new_user()
        assert otp.verify_otp(user, "123456") == (False, "no_code")


def test_resend_timer(app):
    with app.app_context():
        user = new_user()
        assert otp.seconds_until_resend(user) == 0     # nothing sent yet

        otp.issue_otp(user)
        assert 0 < otp.seconds_until_resend(user) <= otp.RESEND_SECONDS

        later = datetime.utcnow() + timedelta(seconds=61)
        assert otp.seconds_until_resend(user, now=later) == 0


# ------------------------------------------------------------------
# Brevo email call (mocked, no network)
# ------------------------------------------------------------------
def test_send_email_calls_brevo_correctly(monkeypatch, brevo_env):
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append((request, timeout))
        return FakeResponse(201)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert otp.send_otp_email("ngo@example.com", "Hope", "482913") is True

    request, timeout = calls[0]
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.get_method() == "POST"
    assert request.get_header("Api-key") == "test-key-123"
    assert request.get_header("Content-type") == "application/json"
    assert timeout == 10

    body = json.loads(request.data)
    assert body["sender"] == {"name": "MealLoop Test",
                              "email": "noreply@example.com"}
    assert body["to"] == [{"email": "ngo@example.com", "name": "Hope"}]
    assert "verification code" in body["subject"]
    assert "482913" in body["htmlContent"]


def test_send_email_escapes_the_name(monkeypatch, brevo_env):
    calls = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda request, timeout=None: calls.append(request)
        or FakeResponse(201))

    otp.send_otp_email("a@example.com", "<b>Evil</b>", "123456")

    html = json.loads(calls[0].data)["htmlContent"]
    assert "<b>Evil</b>" not in html
    assert "&lt;b&gt;" in html


def test_no_api_key_uses_demo_mode(monkeypatch, capsys):
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("no network call is allowed without a key")

    monkeypatch.setattr(urllib.request, "urlopen", must_not_be_called)

    assert otp.send_otp_email("a@example.com", "A", "654321") is False
    printed = capsys.readouterr().out
    assert "demo mode" in printed
    assert "654321" in printed                    # code is in the log


def test_missing_sender_email_uses_demo_mode(monkeypatch, capsys):
    monkeypatch.setenv("BREVO_API_KEY", "test-key-123")   # no sender set

    assert otp.send_otp_email("a@example.com", "A", "654321") is False
    assert "654321" in capsys.readouterr().out


def test_network_failure_falls_back_and_hides_the_key(
        monkeypatch, brevo_env, capsys):
    def no_internet(request, timeout=None):
        raise urllib.error.URLError("no internet")

    monkeypatch.setattr(urllib.request, "urlopen", no_internet)

    assert otp.send_otp_email("a@example.com", "A", "654321") is False
    printed = capsys.readouterr().out
    assert "654321" in printed
    assert "test-key-123" not in printed          # never log the key


def test_brevo_rejecting_the_key_falls_back(monkeypatch, brevo_env, capsys):
    def unauthorized(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized",
                                     {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", unauthorized)

    assert otp.send_otp_email("a@example.com", "A", "654321") is False
    assert "654321" in capsys.readouterr().out


def test_non_success_status_falls_back(monkeypatch, brevo_env, capsys):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda request, timeout=None: FakeResponse(500))

    assert otp.send_otp_email("a@example.com", "A", "654321") is False
    assert "654321" in capsys.readouterr().out


# ------------------------------------------------------------------
# Routes with OTP OFF: exactly the old behaviour
# ------------------------------------------------------------------
def test_otp_off_register_and_login_work_as_before(client, app, sent):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    response = login(client, EMAIL)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/provider/dashboard")

    assert sent == []                              # no email was sent
    with app.app_context():
        assert EmailOtp.query.count() == 0


def test_otp_off_verify_page_redirects_to_login(client):
    response = client.get("/auth/verify")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


# ------------------------------------------------------------------
# Routes with OTP ON
# ------------------------------------------------------------------
def test_register_sends_code_and_goes_to_verify(client, app, otp_on, sent):
    response = register(client)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/verify")
    assert user_value(app, EMAIL, "email_verified") is False
    assert len(sent) == 1
    assert sent[0][0] == EMAIL
    assert len(sent[0][1]) == 6


def test_verify_page_shows_masked_email(client, otp_on, sent):
    register(client)

    response = client.get("/auth/verify")
    assert response.status_code == 200
    assert b"Verify your email" in response.data
    assert b"c***@example.com" in response.data
    assert EMAIL.encode() not in response.data     # full email is hidden


def test_correct_code_then_login_works(client, app, otp_on, sent):
    register(client)
    code = sent[0][1]

    response = client.post("/auth/verify", data={"code": code})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
    assert user_value(app, EMAIL, "email_verified") is True

    response = login(client, EMAIL)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/provider/dashboard")


def test_wrong_code_shows_message_and_stays(client, app, otp_on, sent):
    register(client)
    bad = wrong_code_for(sent[0][1])

    response = client.post("/auth/verify", data={"code": bad})
    assert response.status_code == 200
    assert b"Wrong code" in response.data
    assert b"4 tries left" in response.data
    assert user_value(app, EMAIL, "email_verified") is False


def test_unverified_user_cannot_log_in(client, otp_on, sent):
    register(client)

    response = login(client, EMAIL)           # correct password
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/verify")

    # ...and they are NOT logged in
    page = client.get("/_test/provider-only")
    assert page.status_code == 302
    assert "/auth/login" in page.headers["Location"]
    assert len(sent) == 1                     # no second email so soon


def test_old_user_without_verified_email_is_sent_to_verify(
        client, app, otp_on, sent):
    make_user(app, email="old@example.com", email_verified=False)

    response = login(client, "old@example.com")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/verify")
    assert sent[0][0] == "old@example.com"    # a code was sent for them


def test_verified_user_logs_in_normally(client, app, otp_on, sent):
    make_user(app, email="ok@example.com", email_verified=True)

    response = login(client, "ok@example.com")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/provider/dashboard")
    assert sent == []


def test_verified_admin_logs_in_with_otp_on(client, app, otp_on, sent):
    make_user(app, email="admin@example.com", role="admin",
              email_verified=True)

    response = login(client, "admin@example.com")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/dashboard")


def test_wrong_password_is_still_rejected(client, app, otp_on, sent):
    make_user(app, email="ok@example.com", email_verified=True)

    response = login(client, "ok@example.com", password="nope-nope")
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_verify_without_registering_goes_to_login(client, otp_on):
    response = client.get("/auth/verify")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_resend_is_refused_within_60_seconds(client, otp_on, sent):
    register(client)

    response = client.post("/auth/resend", follow_redirects=True)
    assert response.status_code == 200
    assert b"Please wait" in response.data
    assert len(sent) == 1                     # no new email


def test_resend_after_60_seconds_sends_a_new_code(client, app, otp_on, sent):
    register(client)
    old_code = sent[0][1]
    age_last_sent(app, EMAIL, 120)

    response = client.post("/auth/resend")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/verify")
    assert len(sent) == 2
    new_code = sent[1][1]

    # the old code stops working, the new one works
    if old_code != new_code:
        page = client.post("/auth/verify", data={"code": old_code})
        assert b"Wrong code" in page.data
    response = client.post("/auth/verify", data={"code": new_code})
    assert response.headers["Location"].endswith("/auth/login")
    assert user_value(app, EMAIL, "email_verified") is True


def test_resend_without_registering_goes_to_login(client, otp_on):
    response = client.post("/auth/resend")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_resend_only_accepts_post(client, otp_on):
    assert client.get("/auth/resend").status_code == 405


def test_email_failure_never_crashes_registration(client, app, otp_on,
                                                  capsys):
    # No `sent` fixture here: the real sender runs, with no Brevo key
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/verify")

    page = client.get("/auth/verify")
    assert page.status_code == 200
    assert b"server log" in page.data          # friendly message
    printed = capsys.readouterr().out
    assert "demo mode" in printed              # code went to the log
    assert user_value(app, EMAIL, "email_verified") is False
