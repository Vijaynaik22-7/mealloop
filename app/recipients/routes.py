"""Recipient (NGO) module - Member 2.

Step 1: recipient profile edit page.
Step 2: browse available donations (verified recipients only).
"""
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.utils import role_required
from app.extensions import db
from app.models import Donation, User

# Member 3 writes this function. Until it exists, use a stub that
# returns 0, so the page still works (all donations tie on score).
try:
    from app.matching.priority import calculate_priority_score
except ImportError:
    def calculate_priority_score(donation, recipient, now=None):
        return 0

# create_app looks for a Blueprint named `bp` in this file.
# url_prefix means every route below starts with /recipient
bp = Blueprint("recipients", __name__, url_prefix="/recipient")


def validate_profile(form):
    """Check the submitted form.

    Returns (clean_data, errors). If errors is empty, clean_data is safe
    to save on the user.
    """
    errors = []
    name = (form.get("name") or "").strip()
    address = (form.get("address") or "").strip()
    capacity_raw = (form.get("capacity_people") or "").strip()

    if not name:
        errors.append("Organisation name is required.")
    elif len(name) > 120:
        errors.append("Name must be 120 characters or fewer.")

    if not address:
        errors.append("Address is required.")

    capacity = None
    try:
        capacity = int(capacity_raw)
        if capacity < 1:
            errors.append("Capacity must be at least 1 person.")
    except ValueError:
        errors.append("Capacity must be a whole number.")

    clean = {"name": name, "address": address, "capacity_people": capacity}
    return clean, errors


@bp.route("/profile", methods=["GET", "POST"])
@role_required("recipient")
def edit_profile():
    """Show and save the logged-in recipient's profile.

    A recipient is just a User with role 'recipient', so the profile
    fields (name, address, capacity_people) live on current_user.
    Unverified recipients may edit their profile too.
    """
    if request.method == "POST":
        clean, errors = validate_profile(request.form)
        if errors:
            for message in errors:
                flash(message, "danger")
            # Show what the user typed, not the old saved values
            return render_template(
                "recipients/edit_profile.html", form=request.form
            ), 400

        current_user.name = clean["name"]
        current_user.address = clean["address"]
        current_user.capacity_people = clean["capacity_people"]
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("recipients.edit_profile"))

    # GET: pre-fill the form with the saved values
    saved = {
        "name": current_user.name,
        "address": current_user.address,
        "capacity_people": current_user.capacity_people,
    }
    return render_template("recipients/edit_profile.html", form=saved)


@bp.route("/donations")
@role_required("recipient")
def browse_donations():
    """List donations this recipient can request, best match first."""
    # Unverified NGOs only see a "pending approval" message
    if not current_user.is_verified:
        return render_template(
            "recipients/donations.html", verified=False, items=[]
        )

    now = datetime.now()  # use the same clock the provider module uses

    # One query: each available, not-yet-expired donation with its provider
    rows = (
        db.session.query(Donation, User)
        .join(User, Donation.provider_id == User.id)
        .filter(Donation.status == "available")
        .filter(Donation.expiry_time > now)
        .all()
    )

    recipient = current_user._get_current_object()
    items = []
    for donation, provider in rows:
        score = calculate_priority_score(donation, recipient, now=now)
        items.append(
            {"donation": donation, "provider": provider, "score": score}
        )

    # Highest score first; if scores tie, the one expiring soonest first
    items.sort(key=lambda i: (-i["score"], i["donation"].expiry_time))

    return render_template(
        "recipients/donations.html", verified=True, items=items
    )
