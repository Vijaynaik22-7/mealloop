"""Tests for the build version shown in the footer and at /version."""
from app import create_app


def make_client(sha="abc1234"):
    # In-memory database so tests never touch the real one
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "BUILD_SHA": sha,
    })
    return app.test_client()


def test_version_endpoint_returns_build_sha():
    response = make_client("abc1234").get("/version")

    assert response.status_code == 200
    assert response.get_json() == {"version": "abc1234"}


def test_footer_shows_build_sha():
    response = make_client("abc1234").get("/")

    assert response.status_code == 200
    assert b"abc1234" in response.data


def test_health_is_unchanged():
    response = make_client().get("/health")

    assert response.get_json() == {"status": "ok"}
