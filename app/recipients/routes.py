"""Recipient (NGO) module - Member 2.

Step 1: recipient profile edit page.
Step 2: browse available donations (verified recipients only).
Step 3: request a donation.
Step 4: provider accepts or rejects a request.
Step 5: mark a request as collected.
Step 6: recipient dashboard.
"""
from datetime import datetime

from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from app.auth.utils import role_required
from app.extensions import db
from app.models import Donation, DonationRequest, User
from app.providers.whatsapp import notify_request_accepted
from app.recipients.directions import directions_url
from app.recipients.distance import (
    best_distance_label, has_location, road_distance_enabled,
    road_distances_km,
)
from app.recipients.expiry import expiry_badge
from app.recipients.mapdata import map_markers, maps_api_key

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

# Where people land after an action
PROVIDER_DASHBOARD = "/provider/dashboard"    # Member 1's page
RECIPIENT_DASHBOARD = "/recipient/dashboard"  # our dashboard (step 6)


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

    # Road distance for ALL donations in one call. If it is switched off
    # or fails, this stays empty and we show the straight-line distance.
    road = {}
    if road_distance_enabled():
        road = road_distances_km(recipient, [d for d, _ in rows])

    items = []
    for donation, provider in rows:
        # The priority score always uses the straight-line distance
        score = calculate_priority_score(donation, recipient, now=now)
        label = best_distance_label(
            recipient, donation, road.get(donation.id))
        items.append(
            {"donation": donation, "provider": provider, "score": score,
             "distance": label,
             # Google Maps link (None if we know no destination at all)
             "directions": directions_url(donation),
             # Badge text and colour: "Expires in 3h", "Expiring soon"...
             "expiry": expiry_badge(donation.expiry_time, now=now)}
        )

    # Highest score first; if scores tie, the one expiring soonest first
    items.sort(key=lambda i: (-i["score"], i["donation"].expiry_time))

    # The template asks the NGO to add a location if it has none
    return render_template(
        "recipients/donations.html", verified=True, items=items,
        ngo_has_location=has_location(recipient),
        # Map extras: markers for donations with coordinates, and the key
        # (None if GOOGLE_MAPS_API_KEY is not set, then no map is shown)
        markers=map_markers(items),
        maps_api_key=maps_api_key(),
    )


@bp.route("/donations/<int:donation_id>/request", methods=["POST"])
@role_required("recipient")
def request_donation(donation_id):
    """Create a pending request for a donation."""
    # Only verified NGOs may request food
    if not current_user.is_verified:
        abort(403)

    donation = db.session.get(Donation, donation_id)
    if donation is None:
        abort(404)

    # Someone else may have requested it first, or it may have expired
    now = datetime.now()
    if donation.status != "available" or donation.expiry_time <= now:
        flash("Sorry, this donation is no longer available.", "warning")
        return redirect(url_for("recipients.browse_donations"))

    # people_to_serve must be a whole number from 1 up to our capacity
    try:
        people = int(request.form.get("people_to_serve", ""))
    except ValueError:
        people = 0
    if people < 1:
        flash("Enter how many people you will serve (at least 1).", "danger")
        return redirect(url_for("recipients.browse_donations"))
    capacity = current_user.capacity_people
    if capacity and people > capacity:
        flash(
            f"You can serve at most {capacity} people (your capacity).",
            "danger",
        )
        return redirect(url_for("recipients.browse_donations"))

    recipient = current_user._get_current_object()
    score = calculate_priority_score(donation, recipient, now=now)

    new_request = DonationRequest(
        donation_id=donation.id,
        recipient_id=recipient.id,
        people_to_serve=people,
        status="pending",
        priority_score=float(score),
    )
    donation.status = "requested"  # takes it off the browse list
    db.session.add(new_request)
    db.session.commit()

    flash("Request sent! The provider will accept or reject it.", "success")
    return redirect(url_for("recipients.dashboard"))


def _get_own_request(request_id):
    """Load a request that belongs to the logged-in provider's donation.

    Stops with 404 if it does not exist, or 403 if the donation belongs
    to a different provider. Returns (donation_request, donation).
    """
    donation_request = db.session.get(DonationRequest, request_id)
    if donation_request is None:
        abort(404)
    donation = db.session.get(Donation, donation_request.donation_id)
    if donation is None:
        abort(404)
    if donation.provider_id != current_user.id:
        abort(403)
    return donation_request, donation


def _other_pending(donation_request):
    """Query: the OTHER pending requests for the same donation."""
    return (
        db.session.query(DonationRequest)
        .filter(DonationRequest.donation_id == donation_request.donation_id)
        .filter(DonationRequest.id != donation_request.id)
        .filter(DonationRequest.status == "pending")
    )


def _split_leftover(donation, needed):
    """If the NGO needs less than the donation holds, keep the rest.

    The accepted donation shrinks to `needed`; the leftover becomes a new
    available donation (same food, expiry and pickup place), so it shows
    up on Find Food again. Returns the leftover quantity (0 if none).
    We treat 1 person to serve as 1 packet.
    """
    if needed < 1 or needed >= donation.quantity:
        return 0
    leftover_quantity = donation.quantity - needed
    leftover = Donation(
        provider_id=donation.provider_id,
        food_name=donation.food_name,
        quantity=leftover_quantity,
        unit=donation.unit,
        prepared_at=donation.prepared_at,
        expiry_time=donation.expiry_time,
        pickup_location=donation.pickup_location,
        latitude=donation.latitude,
        longitude=donation.longitude,
        status="available",
    )
    donation.quantity = needed
    db.session.add(leftover)
    return leftover_quantity


@bp.route("/requests/<int:request_id>/accept", methods=["POST"])
@role_required("provider")
def accept_request(request_id):
    """Provider accepts a request: this NGO gets the food."""
    donation_request, donation = _get_own_request(request_id)

    if donation_request.status != "pending":
        flash("This request was already decided.", "warning")
        return redirect(PROVIDER_DASHBOARD)
    if donation.expiry_time <= datetime.now():
        flash("This donation has expired, so it cannot be accepted.",
              "warning")
        return redirect(PROVIDER_DASHBOARD)

    donation_request.status = "accepted"
    donation.status = "accepted"

    # Only one NGO gets this food, so reject all other pending requests
    _other_pending(donation_request).update(
        {"status": "rejected"}, synchronize_session=False
    )

    # Partial request: the part nobody asked for goes back on the list
    unit = donation.unit
    leftover = _split_leftover(donation, donation_request.people_to_serve)
    db.session.commit()

    # Send the notification only after the acceptance is committed.
    # A messaging failure must not undo the accepted donation request.
    try:
        notification = notify_request_accepted(
            donation_request.recipient, donation
        )
    except Exception:
        # Keep the donation accepted even if an unexpected notification
        # error occurs (for example, a malformed recipient profile).
        notification = {"status": "error", "url": None}

    if leftover:
        flash(
            f"Request accepted. The remaining {leftover} {unit} are back "
            "on the Find Food list.",
            "success",
        )
    else:
        flash("Request accepted.", "success")

    if notification.get("status") == "sent":
        flash("WhatsApp notification sent to the NGO.", "success")
    elif notification.get("status") == "fallback" and notification.get("url"):
        flash(
            "WhatsApp is not configured or unavailable. Open this link "
            "to message the NGO manually: " + notification["url"],
            "info",
        )
    else:
        flash(
            "Request accepted, but the WhatsApp notification could not "
            "be sent. Check the NGO phone number or WhatsApp setup.",
            "warning",
        )

    return redirect(PROVIDER_DASHBOARD)


@bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@role_required("provider")
def reject_request(request_id):
    """Provider rejects a request; the food may open up again."""
    donation_request, donation = _get_own_request(request_id)

    if donation_request.status != "pending":
        flash("This request was already decided.", "warning")
        return redirect(PROVIDER_DASHBOARD)

    donation_request.status = "rejected"

    # If nobody else is waiting, put the food back on the browse list
    if _other_pending(donation_request).count() == 0:
        if donation.status == "requested":
            if donation.expiry_time > datetime.now():
                donation.status = "available"
            else:
                donation.status = "expired"
    db.session.commit()

    flash("Request rejected.", "success")
    return redirect(PROVIDER_DASHBOARD)


@bp.route("/requests/<int:request_id>/collect", methods=["POST"])
@login_required
def collect_request(request_id):
    """Mark an accepted request as collected.

    Allowed for the NGO that made the request, or for the provider who
    owns the donation.
    """
    donation_request = db.session.get(DonationRequest, request_id)
    if donation_request is None:
        abort(404)
    donation = db.session.get(Donation, donation_request.donation_id)
    if donation is None:
        abort(404)

    # Work out who is calling
    owns_request = donation_request.recipient_id == current_user.id
    owns_donation = donation.provider_id == current_user.id
    is_recipient = current_user.role == "recipient" and owns_request
    is_provider = current_user.role == "provider" and owns_donation
    if not (is_recipient or is_provider):
        abort(403)

    back = RECIPIENT_DASHBOARD if is_recipient else PROVIDER_DASHBOARD

    if donation_request.status == "collected":
        flash("This was already marked as collected.", "info")
        return redirect(back)
    if donation_request.status != "accepted":
        flash("Only accepted requests can be marked as collected.",
              "warning")
        return redirect(back)

    donation_request.status = "collected"
    donation_request.collected_at = datetime.utcnow()
    donation.status = "collected"
    db.session.commit()

    flash("Marked as collected. Thank you!", "success")
    return redirect(back)


@bp.route("/dashboard")
@role_required("recipient")
def dashboard():
    """Show all of this recipient's requests and their statuses."""
    # One query: each of my requests with its donation and its provider
    rows = (
        db.session.query(DonationRequest, Donation, User)
        .join(Donation, DonationRequest.donation_id == Donation.id)
        .join(User, Donation.provider_id == User.id)
        .filter(DonationRequest.recipient_id == current_user.id)
        .order_by(DonationRequest.id.desc())  # newest first
        .all()
    )

    counts = {"pending": 0, "accepted": 0, "collected": 0, "rejected": 0}
    items = []
    for donation_request, donation, provider in rows:
        status = donation_request.status
        counts[status] = counts.get(status, 0) + 1
        items.append(
            {"donation": donation, "req": donation_request,
             "provider": provider}
        )

    return render_template(
        "recipients/dashboard.html", items=items, counts=counts
    )
