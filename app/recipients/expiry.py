"""Expiry badge text for the Find Food cards (Member 2)."""
from datetime import datetime, timedelta

# Under this many hours left we say "Expiring soon"
SOON_HOURS = 2


def expiry_badge(expiry_time, now=None):
    """Return {"text": ..., "css": ...} for a donation's expiry time.

    - already past:        "Expired"
    - under 2 hours left:  "Expiring soon"
    - otherwise:           "Expires in 3h" (whole hours, rounded down)

    `now` uses UTC, the same clock the Find Food list uses to hide
    expired food, so the badge never disagrees with the list.
    """
    if now is None:
        now = datetime.utcnow()
    remaining = expiry_time - now
    if remaining <= timedelta(0):
        return {"text": "Expired", "css": "bg-secondary"}
    if remaining < timedelta(hours=SOON_HOURS):
        return {"text": "Expiring soon", "css": "bg-danger"}
    hours = int(remaining.total_seconds() // 3600)
    return {"text": f"Expires in {hours}h", "css": "bg-success"}
