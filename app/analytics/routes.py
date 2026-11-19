
"""Impact analytics routes for MealLoop."""

import time

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import User, Donation, DonationRequest
from app.matching.priority import expire_old_donations


bp = Blueprint("analytics", __name__, url_prefix="/analytics")

# Indicative estimated emissions avoided per meal served.
CO2_KG_PER_MEAL = 0.238

EXPIRY_CHECK_INTERVAL = 60
_last_expiry_check = None


@bp.before_app_request
def automatic_donation_expiry():
    """Expire old donations at most once every 60 seconds."""

    global _last_expiry_check

    if request.method != "GET":
        return

    current_time = time.monotonic()

    if (
        _last_expiry_check is not None
        and current_time - _last_expiry_check < EXPIRY_CHECK_INTERVAL
    ):
        return

    _last_expiry_check = current_time

    try:
        expire_old_donations(db.session)
    except Exception:
        # Expiry errors must never interrupt the current request.
        pass


def get_impact_data():
    """Calculate platform impact statistics."""

    completed_donations = Donation.query.filter_by(
        status="collected"
    ).count()

    # Count people served through successfully collected requests.
    total_meals = (
        db.session.query(
            func.coalesce(func.sum(DonationRequest.people_to_serve), 0)
        )
        .filter_by(status="collected")
        .scalar()
    )

    total_meals = int(total_meals or 0)

    # Keep different quantity units separate.
    quantity_rows = (
        db.session.query(
            Donation.unit,
            func.sum(Donation.quantity)
        )
        .filter_by(status="collected")
        .group_by(Donation.unit)
        .order_by(Donation.unit)
        .all()
    )

    rescued_quantities = [
        {
            "unit": unit,
            "quantity": int(quantity or 0)
        }
        for unit, quantity in quantity_rows
    ]

    estimated_co2_saved = round(
        total_meals * CO2_KG_PER_MEAL, 2
    )

    # The model has verification status, but no separate active flag.
    active_providers = User.query.filter_by(
        role="provider",
        is_verified=True
    ).count()

    verified_ngos = User.query.filter_by(
        role="recipient",
        is_verified=True
    ).count()

    top_provider_rows = (
        db.session.query(
            User.name,
            func.count(Donation.id).label("collected_count")
        )
        .join(Donation, Donation.provider_id == User.id)
        .filter(
            User.role == "provider",
            Donation.status == "collected"
        )
        .group_by(User.id, User.name)
        .order_by(
            func.count(Donation.id).desc(),
            User.name.asc()
        )
        .limit(3)
        .all()
    )

    top_providers = [
        {
            "name": name,
            "collected_count": count
        }
        for name, count in top_provider_rows
    ]

    daily_data = (
        db.session.query(
            func.date(Donation.created_at),
            func.count(Donation.id)
        )
        .group_by(func.date(Donation.created_at))
        .order_by(func.date(Donation.created_at))
        .all()
    )

    chart_labels = [str(row[0]) for row in daily_data]
    chart_values = [row[1] for row in daily_data]

    return {
        "completed_donations": completed_donations,
        "total_meals": total_meals,
        "rescued_quantities": rescued_quantities,
        "estimated_co2_saved": estimated_co2_saved,
        "co2_factor": CO2_KG_PER_MEAL,
        "active_providers": active_providers,
        "verified_ngos": verified_ngos,
        "top_providers": top_providers,
        "chart_labels": chart_labels,
        "chart_values": chart_values
    }


@bp.route("/impact")
@login_required
def impact():
    """Display the impact dashboard."""

    data = get_impact_data()

    return render_template(
        "analytics/impact.html",
        data=data
    )


@bp.cli.command("expire-donations")
def expire_donations_command():
    """Expire donations whose expiry time has passed."""

    count = expire_old_donations(db.session)

    print(f"Successfully expired {count} donations.")
