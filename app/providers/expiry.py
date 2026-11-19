"""Expiry status helpers for the provider dashboard."""
from datetime import datetime, timedelta

SOON_HOURS = 2


def expiry_badge(expiry_time, now=None):
    """Return display text and Bootstrap class for an expiry timestamp.

    The provider forms and dashboard use naive local datetimes, so the
    default clock deliberately uses datetime.now() for consistency.
    """
    if now is None:
        now = datetime.now()

    remaining = expiry_time - now
    if remaining <= timedelta(0):
        return {"text": "Expired", "css": "bg-secondary"}
    if remaining < timedelta(hours=SOON_HOURS):
        total_minutes = max(1, int(remaining.total_seconds() // 60))
        hours, minutes = divmod(total_minutes, 60)
        if hours:
            label = f"{hours}h {minutes}m"
        else:
            label = f"{minutes}m"
        return {
            "text": f"Expiring soon · {label}",
            "css": "bg-warning text-dark",
        }

    total_minutes = int(remaining.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        label = f"{days}d {hours}h"
    elif minutes:
        label = f"{hours}h {minutes}m"
    else:
        label = f"{hours}h"
    return {"text": f"Expires in {label}", "css": "bg-success"}
