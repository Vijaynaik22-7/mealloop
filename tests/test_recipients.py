"""Tests for the recipient (NGO) and admin modules - Member 2."""
from datetime import datetime, timedelta

import pytest
from jinja2 import ChoiceLoader, DictLoader
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Donation, DonationRequest, User

# Used only if the real base.html does not exist yet
STAND_IN_BASE = (
    "<html><head><title>{% block title %}{% endblock %}</title></head>"
    "<body>{% block content %}{% endblock %}</body></html>"
)


# ---------------------------------------------------------------- setup

@pytest.fixture()
def app(monkeypatch):
    """A fresh app with an empty in-memory database for every test."""
    # Pin the score so Member 3's real formula cannot change our results
    monkeypatch.setattr(
        "app.recipients.routes.calculate_priority_score",
        lambda donation, recipient, now=None: 0,
    )
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    app.jinja_env.loader = ChoiceLoader([
        app.jinja_env.loader,
        DictLoader({"base.html": STAND_IN_BASE}),
    ])
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def make_user(app, name, role, verified=True, capacity=50):
    with app.app_context():
        user = User(
            name=name, email=f"{name.lower()}@test.com", role=role,
            password_hash=generate_password_hash("pass1234"),
            address="Somewhere", capacity_people=capacity,
            is_verified=verified,
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def make_donation(app, provider_id, name, hours=3, status="available"):
    now = datetime.utcnow()
    with app.app_context():
        donation = Donation(
            provider_id=provider_id, food_name=name, quantity=10,
            unit="kg", prepared_at=now - timedelta(hours=1),
            expiry_time=now + timedelta(hours=hours),
            pickup_location="Main Canteen", status=status,
        )
        db.session.add(donation)
        db.session.commit()
        return donation.id


def make_request(app, donation_id, recipient_id, status="pending"):
    with app.app_context():
        req = DonationRequest(
            donation_id=donation_id, recipient_id=recipient_id,
            people_to_serve=10, status=status, priority_score=0.0,
        )
        db.session.add(req)
        db.session.commit()
        return req.id


def login(app, user_id):
    """A test browser that is already logged in as user_id."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return client


def get_page(app, user_id, url):
    return login(app, user_id).get(url).data.decode()


def field(app, model, row_id, attr):
    """Read one column of one row, using a fresh database session."""
    with app.app_context():
        return getattr(db.session.get(model, row_id), attr)


def count(app, model):
    with app.app_context():
        return db.session.query(model).count()


@pytest.fixture()
def world(app):
    """A provider, two verified NGOs, one unverified NGO and an admin."""
    return {
        "provider": make_user(app, "Provider", "provider"),
        "other_provider": make_user(app, "Provider2", "provider"),
        "ngo": make_user(app, "Ngo", "recipient"),
        "ngo2": make_user(app, "Ngo2", "recipient"),
        "newbie": make_user(app, "Newbie", "recipient", verified=False),
        "admin": make_user(app, "Admin", "admin"),
    }


# ------------------------------------------------------ profile edit

def test_profile_edit_saves_valid_data(app, world):
    client = login(app, world["ngo"])
    response = client.post("/recipient/profile", data={
        "name": "Helping Hands", "address": "5 Church St",
        "capacity_people": "80",
    })
    assert response.status_code == 302
    assert field(app, User, world["ngo"], "name") == "Helping Hands"
    assert field(app, User, world["ngo"], "capacity_people") == 80


@pytest.mark.parametrize("name,address,capacity", [
    ("", "5 Church St", "10"),
    ("Helping Hands", "", "10"),
    ("Helping Hands", "5 Church St", "0"),
    ("Helping Hands", "5 Church St", "abc"),
])
def test_profile_edit_rejects_bad_data(app, world, name, address, capacity):
    client = login(app, world["ngo"])
    response = client.post("/recipient/profile", data={
        "name": name, "address": address, "capacity_people": capacity,
    })
    assert response.status_code == 400
    assert field(app, User, world["ngo"], "name") == "Ngo"


# ------------------------------------------------------ browsing

def test_unverified_sees_pending_message_not_food(app, world):
    make_donation(app, world["provider"], "SoonRice")
    page = get_page(app, world["newbie"], "/recipient/donations")
    assert "pending approval" in page
    assert "SoonRice" not in page


def test_verified_sees_only_available_unexpired_food(app, world):
    provider = world["provider"]
    make_donation(app, provider, "FreshRice")
    make_donation(app, provider, "OldBread", hours=-3)
    make_donation(app, provider, "TakenCurry", status="requested")
    page = get_page(app, world["ngo"], "/recipient/donations")
    assert "FreshRice" in page
    assert "OldBread" not in page
    assert "TakenCurry" not in page


def test_browse_sorts_by_priority_score(app, world, monkeypatch):
    provider = world["provider"]
    make_donation(app, provider, "LowScore", hours=1)
    make_donation(app, provider, "HighScore", hours=9)
    monkeypatch.setattr(
        "app.recipients.routes.calculate_priority_score",
        lambda donation, recipient, now=None: (
            100 if donation.food_name == "HighScore" else 1),
    )
    page = get_page(app, world["ngo"], "/recipient/donations")
    assert page.find("HighScore") < page.find("LowScore")


def test_browse_ties_go_to_soonest_expiry(app, world):
    provider = world["provider"]
    make_donation(app, provider, "LaterDal", hours=5)
    make_donation(app, provider, "SoonRice", hours=2)
    page = get_page(app, world["ngo"], "/recipient/donations")
    assert page.find("SoonRice") < page.find("LaterDal")


# ------------------------------------------------------ requesting

def test_unverified_cannot_request(app, world):
    donation = make_donation(app, world["provider"], "SoonRice")
    response = login(app, world["newbie"]).post(
        f"/recipient/donations/{donation}/request",
        data={"people_to_serve": "10"},
    )
    assert response.status_code == 403
    assert count(app, DonationRequest) == 0
    assert field(app, Donation, donation, "status") == "available"


def test_verified_request_creates_pending_request(app, world):
    donation = make_donation(app, world["provider"], "SoonRice")
    response = login(app, world["ngo"]).post(
        f"/recipient/donations/{donation}/request",
        data={"people_to_serve": "20"},
    )
    assert response.status_code == 302
    assert count(app, DonationRequest) == 1
    with app.app_context():
        req = db.session.query(DonationRequest).first()
        assert req.status == "pending"
        assert req.people_to_serve == 20
        assert req.recipient_id == world["ngo"]
    assert field(app, Donation, donation, "status") == "requested"


def test_requested_food_leaves_browse_list(app, world):
    donation = make_donation(app, world["provider"], "SoonRice")
    login(app, world["ngo"]).post(
        f"/recipient/donations/{donation}/request",
        data={"people_to_serve": "5"},
    )
    page = get_page(app, world["ngo2"], "/recipient/donations")
    assert "SoonRice" not in page


def test_cannot_request_taken_or_expired_food(app, world):
    taken = make_donation(app, world["provider"], "Taken",
                          status="requested")
    expired = make_donation(app, world["provider"], "Old", hours=-2)
    client = login(app, world["ngo"])
    for donation in (taken, expired):
        client.post(f"/recipient/donations/{donation}/request",
                    data={"people_to_serve": "5"})
    assert count(app, DonationRequest) == 0


@pytest.mark.parametrize("people", ["0", "-3", "abc", "", "80"])
def test_bad_people_to_serve_is_rejected(app, world, people):
    donation = make_donation(app, world["provider"], "SoonRice")
    login(app, world["ngo"]).post(
        f"/recipient/donations/{donation}/request",
        data={"people_to_serve": people},   # 80 is over capacity (50)
    )
    assert count(app, DonationRequest) == 0
    assert field(app, Donation, donation, "status") == "available"


def test_missing_donation_gives_404(app, world):
    response = login(app, world["ngo"]).post(
        "/recipient/donations/9999/request",
        data={"people_to_serve": "5"},
    )
    assert response.status_code == 404


def test_provider_cannot_request_food(app, world):
    donation = make_donation(app, world["provider"], "SoonRice")
    login(app, world["other_provider"]).post(
        f"/recipient/donations/{donation}/request",
        data={"people_to_serve": "5"},
    )
    assert count(app, DonationRequest) == 0


# ------------------------------------------------------ accept / reject

def test_provider_accept_rejects_the_other_requests(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    first = make_request(app, donation, world["ngo"])
    second = make_request(app, donation, world["ngo2"])
    response = login(app, world["provider"]).post(
        f"/recipient/requests/{first}/accept")
    assert response.status_code == 302
    assert field(app, DonationRequest, first, "status") == "accepted"
    assert field(app, DonationRequest, second, "status") == "rejected"
    assert field(app, Donation, donation, "status") == "accepted"


def test_other_provider_cannot_decide(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    req = make_request(app, donation, world["ngo"])
    client = login(app, world["other_provider"])
    assert client.post(
        f"/recipient/requests/{req}/accept").status_code == 403
    assert client.post(
        f"/recipient/requests/{req}/reject").status_code == 403
    assert field(app, DonationRequest, req, "status") == "pending"


def test_recipient_cannot_accept_own_request(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    req = make_request(app, donation, world["ngo"])
    login(app, world["ngo"]).post(f"/recipient/requests/{req}/accept")
    assert field(app, DonationRequest, req, "status") == "pending"


def test_reject_only_request_puts_food_back(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    req = make_request(app, donation, world["ngo"])
    login(app, world["provider"]).post(f"/recipient/requests/{req}/reject")
    assert field(app, DonationRequest, req, "status") == "rejected"
    assert field(app, Donation, donation, "status") == "available"
    page = get_page(app, world["ngo2"], "/recipient/donations")
    assert "SoonRice" in page


def test_reject_keeps_food_reserved_if_another_is_waiting(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    first = make_request(app, donation, world["ngo"])
    second = make_request(app, donation, world["ngo2"])
    login(app, world["provider"]).post(
        f"/recipient/requests/{first}/reject")
    assert field(app, Donation, donation, "status") == "requested"
    assert field(app, DonationRequest, second, "status") == "pending"


def test_decided_request_cannot_be_decided_again(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    req = make_request(app, donation, world["ngo"])
    client = login(app, world["provider"])
    client.post(f"/recipient/requests/{req}/accept")
    client.post(f"/recipient/requests/{req}/reject")
    assert field(app, DonationRequest, req, "status") == "accepted"


def test_expired_food_cannot_be_accepted(app, world):
    donation = make_donation(app, world["provider"], "Old", hours=-1,
                             status="requested")
    req = make_request(app, donation, world["ngo"])
    login(app, world["provider"]).post(f"/recipient/requests/{req}/accept")
    assert field(app, DonationRequest, req, "status") == "pending"


# ------------------------------------------------------ collection

def test_recipient_marks_collected(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="accepted")
    req = make_request(app, donation, world["ngo"], status="accepted")
    response = login(app, world["ngo"]).post(
        f"/recipient/requests/{req}/collect")
    assert response.status_code == 302
    assert field(app, DonationRequest, req, "status") == "collected"
    assert field(app, DonationRequest, req, "collected_at") is not None
    assert field(app, Donation, donation, "status") == "collected"


def test_provider_marks_collected(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="accepted")
    req = make_request(app, donation, world["ngo"], status="accepted")
    login(app, world["provider"]).post(f"/recipient/requests/{req}/collect")
    assert field(app, DonationRequest, req, "status") == "collected"
    assert field(app, Donation, donation, "status") == "collected"


def test_only_accepted_requests_can_be_collected(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    req = make_request(app, donation, world["ngo"], status="pending")
    login(app, world["ngo"]).post(f"/recipient/requests/{req}/collect")
    assert field(app, DonationRequest, req, "status") == "pending"
    assert field(app, DonationRequest, req, "collected_at") is None


def test_collect_twice_changes_nothing(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="accepted")
    req = make_request(app, donation, world["ngo"], status="accepted")
    client = login(app, world["ngo"])
    client.post(f"/recipient/requests/{req}/collect")
    first_time = field(app, DonationRequest, req, "collected_at")
    client.post(f"/recipient/requests/{req}/collect")
    assert field(app, DonationRequest, req, "collected_at") == first_time


def test_strangers_cannot_mark_collected(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="accepted")
    req = make_request(app, donation, world["ngo"], status="accepted")
    for stranger in (world["ngo2"], world["other_provider"]):
        response = login(app, stranger).post(
            f"/recipient/requests/{req}/collect")
        assert response.status_code == 403
    assert field(app, DonationRequest, req, "status") == "accepted"


# ------------------------------------------------------ dashboard

def test_dashboard_shows_only_my_requests_with_statuses(app, world):
    provider = world["provider"]
    mine = make_donation(app, provider, "MyRice", status="accepted")
    theirs = make_donation(app, provider, "SecretDal", status="requested")
    make_request(app, mine, world["ngo"], status="accepted")
    make_request(app, theirs, world["ngo2"])
    page = get_page(app, world["ngo"], "/recipient/dashboard")
    assert "MyRice" in page
    assert "Accepted" in page
    assert "SecretDal" not in page


def test_dashboard_button_only_for_accepted_requests(app, world):
    provider = world["provider"]
    accepted = make_donation(app, provider, "A", status="accepted")
    pending = make_donation(app, provider, "B", status="requested")
    make_request(app, accepted, world["ngo"], status="accepted")
    make_request(app, pending, world["ngo"], status="pending")
    page = get_page(app, world["ngo"], "/recipient/dashboard")
    assert page.count("Mark collected") == 1


def test_dashboard_is_for_recipients_only(app, world):
    assert login(app, world["provider"]).get(
        "/recipient/dashboard").status_code != 200
    assert app.test_client().get(
        "/recipient/dashboard").status_code != 200


# ------------------------------------------------------ admin

def test_admin_lists_only_unverified_recipients(app, world):
    page = get_page(app, world["admin"], "/admin/recipients")
    assert "Newbie" in page
    assert "Ngo2" not in page
    assert "Provider" not in page


def test_admin_approval_unlocks_requesting(app, world):
    donation = make_donation(app, world["provider"], "SoonRice")
    url = f"/recipient/donations/{donation}/request"
    newbie = world["newbie"]

    # Before approval: blocked
    assert login(app, newbie).post(
        url, data={"people_to_serve": "5"}).status_code == 403

    response = login(app, world["admin"]).post(
        f"/admin/recipients/{newbie}/approve")
    assert response.status_code == 302
    assert field(app, User, newbie, "is_verified") is True

    # After approval: the same request works
    assert login(app, newbie).post(
        url, data={"people_to_serve": "5"}).status_code == 302
    assert count(app, DonationRequest) == 1


def test_approving_twice_is_harmless(app, world):
    client = login(app, world["admin"])
    client.post(f"/admin/recipients/{world['newbie']}/approve")
    response = client.post(f"/admin/recipients/{world['newbie']}/approve")
    assert response.status_code == 302
    assert field(app, User, world["newbie"], "is_verified") is True


def test_only_admin_can_approve(app, world):
    for user in (world["ngo"], world["provider"], world["newbie"]):
        login(app, user).post(
            f"/admin/recipients/{world['newbie']}/approve")
    assert field(app, User, world["newbie"], "is_verified") is False
    assert app.test_client().get("/admin/dashboard").status_code != 200


def test_approve_unknown_or_non_recipient_gives_404(app, world):
    client = login(app, world["admin"])
    assert client.post("/admin/recipients/9999/approve").status_code == 404
    assert client.post(
        f"/admin/recipients/{world['provider']}/approve"
    ).status_code == 404


def test_admin_reject_removes_unverified_ngo(app, world):
    response = login(app, world["admin"]).post(
        f"/admin/recipients/{world['newbie']}/reject")
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, world["newbie"]) is None


def test_admin_cannot_reject_verified_ngo_or_one_with_requests(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    make_request(app, donation, world["newbie"])
    client = login(app, world["admin"])
    client.post(f"/admin/recipients/{world['ngo']}/reject")
    client.post(f"/admin/recipients/{world['newbie']}/reject")
    with app.app_context():
        assert db.session.get(User, world["ngo"]) is not None
        assert db.session.get(User, world["newbie"]) is not None


def test_admin_dashboard_numbers(app, world):
    donation = make_donation(app, world["provider"], "SoonRice",
                             status="requested")
    make_request(app, donation, world["ngo"])
    page = get_page(app, world["admin"], "/admin/dashboard")
    assert 'id="stat-pending">1</div>' in page
    assert 'id="stat-verified">2</div>' in page
    assert 'id="stat-providers">2</div>' in page
    assert 'id="don-requested">1</td>' in page
    assert 'id="req-pending">1</td>' in page
