"""Tests for provider WhatsApp notification helpers."""
from types import SimpleNamespace

from app.providers.whatsapp import (
    build_whatsapp_link,
    notify_request_accepted,
)


def test_build_whatsapp_link_uses_india_default_country_code(monkeypatch):
    monkeypatch.delenv("WHATSAPP_DEFAULT_COUNTRY_CODE", raising=False)
    link = build_whatsapp_link("9876543210", "Request accepted")
    assert link == "https://wa.me/919876543210?text=Request%20accepted"


def test_notification_uses_manual_fallback_without_api_credentials(
    monkeypatch
):
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    recipient = SimpleNamespace(name="Hope NGO", phone="9876543210")
    donation = SimpleNamespace(food_name="Vegetable Rice")

    result = notify_request_accepted(recipient, donation)

    assert result["status"] == "fallback"
    assert result["url"].startswith("https://wa.me/919876543210?")
    assert "Vegetable%20Rice" in result["url"]


def test_notification_reports_missing_phone():
    recipient = SimpleNamespace(name="Hope NGO", phone=None)
    donation = SimpleNamespace(food_name="Rice")

    assert notify_request_accepted(recipient, donation) == {
        "status": "unavailable",
        "url": None,
    }


def test_cloud_api_notification_sends_json(monkeypatch):
    import json
    from app.providers import whatsapp

    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(whatsapp, "urlopen", fake_urlopen)
    recipient = SimpleNamespace(name="Hope NGO", phone="+919876543210")
    donation = SimpleNamespace(food_name="Rice")

    result = whatsapp.notify_request_accepted(recipient, donation)

    assert result == {"status": "sent", "url": None}
    assert captured["url"].endswith("/123456/messages")
    assert captured["payload"]["to"] == "919876543210"
    assert "accepted" in captured["payload"]["text"]["body"]
    assert captured["timeout"] == 8
