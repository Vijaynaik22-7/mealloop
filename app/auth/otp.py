"""Email OTP helpers (used only when OTP_ENABLED=true).

Flow: issue_otp() makes a code and stores its HASH, send_otp_email()
mails it through Brevo, verify_otp() checks what the user typed.

Safety rules in this file:
- The OTP feature is OFF unless the env var OTP_ENABLED is "true".
- If the Brevo key / sender is missing, or the API call fails, the code
  is printed to the server log (demo mode) and nothing crashes.
- Keys are read from environment variables only, never from code.
"""
import json
import os
import secrets
import urllib.request
from datetime import datetime, timedelta
from html import escape

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import EmailOtp

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
OTP_LENGTH = 6
OTP_LIFETIME_MINUTES = 10   # a code stops working after 10 minutes
MAX_ATTEMPTS = 5            # wrong guesses allowed per code
RESEND_SECONDS = 60         # wait this long before sending a new code


def otp_enabled():
    """True only when OTP_ENABLED is exactly "true" (any letter case)."""
    return os.environ.get("OTP_ENABLED", "").strip().lower() == "true"


def generate_code():
    """A random 6-digit code such as '042917' (secrets = safe random)."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def issue_otp(user, now=None):
    """Create (or replace) the user's code. Returns the plain code.

    Only the hash is saved in the database. The caller must send the
    plain code to the user and then forget it.
    """
    now = now or datetime.utcnow()
    code = generate_code()

    record = user.email_otp
    if record is None:
        record = EmailOtp(user_id=user.id)
        db.session.add(record)
    record.code_hash = generate_password_hash(code)
    record.expires_at = now + timedelta(minutes=OTP_LIFETIME_MINUTES)
    record.attempts = 0
    record.last_sent_at = now
    db.session.commit()
    return code


def seconds_until_resend(user, now=None):
    """0 when a new code may be sent, else seconds left to wait."""
    record = user.email_otp
    if record is None or record.last_sent_at is None:
        return 0
    now = now or datetime.utcnow()
    waited = (now - record.last_sent_at).total_seconds()
    return max(0, int(RESEND_SECONDS - waited + 0.999))


def verify_otp(user, typed_code, now=None):
    """Check a typed code. Returns (ok, reason).

    reason is one of: "ok", "format", "no_code", "locked", "expired",
    "wrong". On success the user is marked email_verified and the stored
    code is deleted (so it cannot be used twice).
    """
    now = now or datetime.utcnow()
    typed_code = (typed_code or "").strip()

    # A badly typed code (letters, wrong length) is not counted as a try
    if not (typed_code.isdigit() and len(typed_code) == OTP_LENGTH):
        return False, "format"

    record = user.email_otp
    if record is None:
        return False, "no_code"
    if record.attempts >= MAX_ATTEMPTS:
        return False, "locked"
    if now > record.expires_at:
        return False, "expired"

    if check_password_hash(record.code_hash, typed_code):
        user.email_verified = True
        db.session.delete(record)
        db.session.commit()
        return True, "ok"

    record.attempts += 1
    db.session.commit()
    if record.attempts >= MAX_ATTEMPTS:
        return False, "locked"
    return False, "wrong"


def attempts_left(user):
    """How many wrong guesses the current code still allows."""
    record = user.email_otp
    if record is None:
        return 0
    return max(0, MAX_ATTEMPTS - record.attempts)


def _demo_mode_log(to_email, code, why):
    """Print the code to the server log so the demo can continue."""
    print(f"[MealLoop OTP demo mode] {why}. "
          f"Code for {to_email}: {code}", flush=True)


def send_otp_email(to_email, to_name, code):
    """Send the code with the Brevo HTTP API. Returns True if it was sent.

    Returns False (never raises) when the key or sender is missing or the
    request fails; the code is then printed to the server log instead.
    """
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    from_email = os.environ.get("OTP_FROM_EMAIL", "").strip()
    from_name = os.environ.get("OTP_FROM_NAME", "").strip() or "MealLoop"

    if not api_key or not from_email:
        _demo_mode_log(to_email, code, "BREVO_API_KEY/OTP_FROM_EMAIL not set")
        return False

    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "subject": "Your MealLoop verification code",
        "htmlContent": (
            f"<p>Hi {escape(to_name or '')},</p>"
            f"<p>Your MealLoop verification code is "
            f"<strong style='font-size:20px'>{code}</strong></p>"
            f"<p>It expires in {OTP_LIFETIME_MINUTES} minutes. "
            f"If you did not register, ignore this email.</p>"
        ),
    }
    request = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if 200 <= response.status < 300:
                return True
            _demo_mode_log(to_email, code, f"Brevo answered {response.status}")
            return False
    except Exception as err:  # no internet, bad key, timeout... never crash
        # Print only the error type, never the request (it holds the key)
        _demo_mode_log(to_email, code, f"email failed ({type(err).__name__})")
        return False
