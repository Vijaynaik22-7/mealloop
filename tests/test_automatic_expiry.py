
import pytest

from app import create_app
import app.analytics.routes as analytics_routes


@pytest.fixture
def app():
    return create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret"
    })


def test_expiry_runs_only_once_within_60_seconds(app, monkeypatch):
    calls = []

    times = iter([100.0, 110.0, 161.0])

    monkeypatch.setattr(
        analytics_routes,
        "_last_expiry_check",
        0.0
    )
    monkeypatch.setattr(
        analytics_routes.time,
        "monotonic",
        lambda: next(times)
    )
    monkeypatch.setattr(
        analytics_routes,
        "expire_old_donations",
        lambda session: calls.append(1)
    )

    with app.test_client() as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200

    assert len(calls) == 2


def test_expiry_does_not_run_for_post_requests(app, monkeypatch):
    calls = []

    monkeypatch.setattr(
        analytics_routes,
        "_last_expiry_check",
        0.0
    )
    monkeypatch.setattr(
        analytics_routes.time,
        "monotonic",
        lambda: 100.0
    )
    monkeypatch.setattr(
        analytics_routes,
        "expire_old_donations",
        lambda session: calls.append(1)
    )

    with app.test_client() as client:
        response = client.post("/health")

    assert response.status_code == 405
    assert len(calls) == 0


def test_expiry_error_does_not_break_get_request(app, monkeypatch):
    monkeypatch.setattr(
        analytics_routes,
        "_last_expiry_check",
        0.0
    )
    monkeypatch.setattr(
        analytics_routes.time,
        "monotonic",
        lambda: 100.0
    )

    def raise_error(session):
        raise RuntimeError("Test expiry error")

    monkeypatch.setattr(
        analytics_routes,
        "expire_old_donations",
        raise_error
    )

    with app.test_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
