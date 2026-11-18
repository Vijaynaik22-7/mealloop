"""Admin module - Member 2.

Step 7: admin dashboard and recipient (NGO) verification.
"""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from sqlalchemy import func

from app.auth.utils import role_required
from app.extensions import db
from app.models import Donation, DonationRequest, User

# create_app looks for a Blueprint named `bp` in this file.
bp = Blueprint("admin", __name__, url_prefix="/admin")

DONATION_STATUSES = (
    "available", "requested", "accepted", "collected", "expired",
    "cancelled",
)
REQUEST_STATUSES = ("pending", "accepted", "rejected", "collected")


def _count_by_status(model):
    """Return {status: how many rows} for a model, e.g. Donation."""
    rows = (
        db.session.query(model.status, func.count(model.id))
        .group_by(model.status)
        .all()
    )
    return dict(rows)


def _pending_recipients():
    """Query: recipients that an admin has not approved yet."""
    return (
        db.session.query(User)
        .filter(User.role == "recipient")
        .filter(User.is_verified.is_(False))
        .order_by(User.id)
    )


def _get_recipient_or_404(user_id):
    """Load a user, but only if they are a recipient (NGO)."""
    user = db.session.get(User, user_id)
    if user is None or user.role != "recipient":
        abort(404)
    return user


@bp.route("/dashboard")
@role_required("admin")
def dashboard():
    """Simple overview numbers for the admin."""
    recipients = db.session.query(User).filter(User.role == "recipient")
    stats = {
        "pending": recipients.filter(User.is_verified.is_(False)).count(),
        "verified": recipients.filter(User.is_verified.is_(True)).count(),
        "providers": (
            db.session.query(User).filter(User.role == "provider").count()
        ),
    }
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        donation_counts=_count_by_status(Donation),
        request_counts=_count_by_status(DonationRequest),
        donation_statuses=DONATION_STATUSES,
        request_statuses=REQUEST_STATUSES,
    )


@bp.route("/recipients")
@role_required("admin")
def list_recipients():
    """List NGOs waiting for approval."""
    return render_template(
        "admin/recipients.html", recipients=_pending_recipients().all()
    )


@bp.route("/recipients/<int:user_id>/approve", methods=["POST"])
@role_required("admin")
def approve_recipient(user_id):
    """Verify an NGO so it can request donations."""
    user = _get_recipient_or_404(user_id)

    if user.is_verified:
        flash(f"{user.name} is already verified.", "info")
    else:
        user.is_verified = True
        db.session.commit()
        flash(f"{user.name} has been approved.", "success")
    return redirect(url_for("admin.list_recipients"))


@bp.route("/recipients/<int:user_id>/reject", methods=["POST"])
@role_required("admin")
def reject_recipient(user_id):
    """Reject an applicant: remove the unverified account."""
    user = _get_recipient_or_404(user_id)

    if user.is_verified:
        flash("Verified NGOs cannot be rejected here.", "warning")
        return redirect(url_for("admin.list_recipients"))

    has_requests = (
        db.session.query(DonationRequest)
        .filter(DonationRequest.recipient_id == user.id)
        .count()
    )
    if has_requests:
        flash("This NGO already has requests, so it cannot be removed.",
              "warning")
        return redirect(url_for("admin.list_recipients"))

    name = user.name
    db.session.delete(user)
    db.session.commit()
    flash(f"{name} was rejected and removed.", "success")
    return redirect(url_for("admin.list_recipients"))
