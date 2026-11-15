"""Health check test (used by CI)."""
from app import create_app


def test_health_returns_ok():
    # Use an in-memory database so tests never touch the real one
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
