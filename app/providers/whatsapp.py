
"""WhatsApp notifications for accepted MealLoop donation requests.

Uses Twilio's Programmable Messaging REST API when credentials are configured.
Falls back to a manual wa.me link if sending is unavailable.
"""
import base64
import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)

TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts"


def _normalise_phone(phone):
    """Return a WhatsApp-compatible international number, or None."""
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    if len(digits) == 10:
        country_code = re.sub(
            r"\D",
            "",
            os.environ.get(
                "TWILIO_DEFAULT_COUNTRY_CODE",
                os.environ.get("WHATSAPP_DEFAULT_COUNTRY_CODE", "91"),
            ),
        )
        digits = country_code + digits

    if not 8 <= len(digits) <= 15:
        return None

    return digits


def build_whatsapp_link(phone, message):
    """Build a manual wa.me fallback link; return None for invalid phones."""
    number = _normalise_phone(phone)

    if not number:
        return None

    return f"https://wa.me/{number}?text={quote(message)}"


def _twilio_sender():
    """Return the configured Twilio WhatsApp sender in channel format."""
    sender = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()

    if sender.lower().startswith("whatsapp:"):
        sender = sender.split(":", 1)[1].strip()

    number = _normalise_phone(sender)

    if not number:
        return None

    return f"whatsapp:+{number}"


def notify_request_accepted(recipient, donation):
    """Send an acceptance message or return a manual WhatsApp fallback.

    Returns a dict with status (sent, fallback, or unavailable),
    optional url, and optional Twilio message_sid.
    """
    message = (
        f"Hello {recipient.name}, your request for {donation.food_name} "
        "from MealLoop has been accepted. Please coordinate collection "
        "with the provider."
    )

    phone = _normalise_phone(recipient.phone)

    if not phone:
        return {"status": "unavailable", "url": None}

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    sender = _twilio_sender()

    if account_sid and auth_token and sender:
        endpoint = (
            f"{TWILIO_API_URL}/{account_sid}/Messages.json"
        )

        form_data = urlencode({
            "From": sender,
            "To": f"whatsapp:+{phone}",
            "Body": message,
        }).encode("utf-8")

        credentials = base64.b64encode(
            f"{account_sid}:{auth_token}".encode("utf-8")
        ).decode("ascii")

        request = Request(
            endpoint,
            data=form_data,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))

                if 200 <= response.status < 300:
                    LOGGER.info(
                        "Twilio accepted WhatsApp message: %s",
                        result.get("sid"),
                    )
                    return {
                        "status": "sent",
                        "url": None,
                        "message_sid": result.get("sid"),
                    }

                LOGGER.warning(
                    "Twilio returned HTTP %s",
                    response.status,
                )

        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            LOGGER.warning(
                "Twilio WhatsApp API returned HTTP %s: %s",
                error.code,
                details,
            )

        except (URLError, TimeoutError, OSError, ValueError) as error:
            LOGGER.warning("Twilio WhatsApp notification failed: %s", error)

    return {
        "status": "fallback",
        "url": build_whatsapp_link(recipient.phone, message),
    }
