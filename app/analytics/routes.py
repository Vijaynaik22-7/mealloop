
"""Impact analytics routes for MealLoop."""


from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import User, Donation
from app.matching.priority import expire_old_donations


bp = Blueprint("analytics", __name__, url_prefix="/analytics")

MEALS_PER_UNIT = 1
WASTE_KG_PER_MEAL = 0.25


def get_impact_data():
    """Calculate platform impact statistics."""

    completed_donations = Donation.query.filter_by(
        status="collected"
    ).count()

    total_quantity = (
        db.session.query(
            func.coalesce(func.sum(Donation.quantity), 0)
        )
        .filter_by(status="collected")
        .scalar()
    )

    total_meals = int(total_quantity * MEALS_PER_UNIT)

    waste_avoided = round(
        total_meals * WASTE_KG_PER_MEAL, 2
    )

    active_providers = User.query.filter_by(
        role="provider",
        is_verified=True
    ).count()

    verified_ngos = User.query.filter_by(
        role="recipient",
        is_verified=True
    ).count()

    daily_data = (
        db.session.query(
            func.date(Donation.created_at),
            func.count(Donation.id)
        )
        .group_by(func.date(Donation.created_at))
        .order_by(func.date(Donation.created_at))
        .all()
    )

    chart_labels = [
        str(row[0]) for row in daily_data
    ]

    chart_values = [
        row[1] for row in daily_data
    ]

    return {
        "completed_donations": completed_donations,
        "total_meals": total_meals,
        "waste_avoided": waste_avoided,
        "active_providers": active_providers,
        "verified_ngos": verified_ngos,
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

    print(
        f"Successfully expired {count} donations."
    )
