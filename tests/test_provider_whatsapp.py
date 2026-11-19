
import json
from types import SimpleNamespace
from urllib.parse import parse_qs

from app.providers import whatsapp


def test_build_whatsapp_link_uses_india_default_country_code(monkeypatch):
    monkeypatch.setenv("TWILIO_DEFAULT_COUNTRY_CODE", "91")

    link = whatsapp.build_whatsapp_link("9876543210", "Hello NGO")

    assert link.startswith("https://wa.me/919876543210?")
    assert "Hello" in link


def test_notification_uses_manual_fallback_without_api_credentials(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)

    recipient = SimpleNamespace(
        name="Hope NGO",
        phone="+919876543210",
    )
    donation = SimpleNamespace(food_name="Rice")

    result = whatsapp.notify_request_accepted(recipient, donation)

    assert result["status"] == "fallback"
    assert result["url"].startswith("https://wa.me/919876543210?")


def test_notification_reports_missing_phone():
    recipient = SimpleNamespace(name="Hope NGO", phone="")
    donation = SimpleNamespace(food_name="Rice")

    result = whatsapp.notify_request_accepted(recipient, donation)

    assert result == {"status": "unavailable", "url": None}


def test_twilio_notification_sends_form_data(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv(
        "TWILIO_WHATSAPP_FROM",
        "whatsapp:+14155238886",
    )

    captured = {}

    class FakeResponse:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "sid": "SMtest123",
                "status": "queued",
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["payload"] = parse_qs(
            request.data.decode("utf-8")
        )
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(whatsapp, "urlopen", fake_urlopen)

    recipient = SimpleNamespace(
        name="Hope NGO",
        phone="+919876543210",
    )
    donation = SimpleNamespace(food_name="Rice")

    result = whatsapp.notify_request_accepted(recipient, donation)

    assert result == {
        "status": "sent",
        "url": None,
        "message_sid": "SMtest123",
    }

    assert captured["url"] == (
        "https://api.twilio.com/2010-04-01/"
        "Accounts/ACtest123/Messages.json"
    )
    assert captured["payload"]["From"] == [
        "whatsapp:+14155238886"
    ]
    assert captured["payload"]["To"] == [
        "whatsapp:+919876543210"
    ]
    assert "Hope NGO" in captured["payload"]["Body"][0]
    assert "Rice" in captured["payload"]["Body"][0]
    assert captured["timeout"] == 10
    assert captured["headers"].get("Authorization")
