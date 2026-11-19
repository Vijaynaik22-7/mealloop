
"""WhatsApp notifications for accepted MealLoop donation requests.

When WhatsApp Cloud API credentials are configured, send a text message
using the standard-library urllib client. Otherwise return a wa.me link
that the provider can open to notify the NGO manually.
"""
import json
import logging
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)
GRAPH_API_VERSION = "v21.0"


def _normalise_phone(phone):
    """Return a WhatsApp-compatible international number, or None."""
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    if len(digits) == 10:
        country_code = re.sub(
            r"\D", "",
            os.environ.get("WHATSAPP_DEFAULT_COUNTRY_CODE", "91")
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


def notify_request_accepted(recipient, donation):
    """Send an acceptance message or return a manual WhatsApp fallback.

    Returns a dict with status (sent, fallback, or unavailable)
    and optional url. Notification failures never undo an accepted request.
    """
    message = (
        f"Hello {recipient.name}, your request for {donation.food_name} "
        f"from MealLoop has been accepted. Please coordinate collection "
        "with the provider."
    )

    phone = _normalise_phone(recipient.phone)

    if not phone:
        return {"status": "unavailable", "url": None}

    token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

    if token and phone_number_id:
        endpoint = (
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
            f"{phone_number_id}/messages"
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message,
            },
        }

        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=8) as response:
                if 200 <= response.status < 300:
                    return {"status": "sent", "url": None}

                LOGGER.warning(
                    "WhatsApp API returned HTTP %s",
                    response.status,
                )

        except (HTTPError, URLError, TimeoutError, OSError) as error:
            LOGGER.warning(
                "WhatsApp notification failed: %s",
                error,
            )

    return {
        "status": "fallback",
        "url": build_whatsapp_link(recipient.phone, message),
    }
