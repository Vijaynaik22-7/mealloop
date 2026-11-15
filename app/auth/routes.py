"""Authentication: register, login, logout."""
from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.utils import redirect_to_dashboard
from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Admin is NOT allowed here: admins are created by create_admin.py only
SELF_REGISTER_ROLES = ("provider", "recipient")


def _to_float(value):
    """Turn form text into a float, or None if blank/invalid."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_safe_next(target):
    """Only allow redirects to pages inside our own site."""
    return bool(target) and target.startswith("/") \
        and not target.startswith("//")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect_to_dashboard(current_user)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "")
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        latitude = _to_float(request.form.get("latitude"))
        longitude = _to_float(request.form.get("longitude"))
        capacity = request.form.get("capacity_people", "").strip()

        # ---- validation: collect all problems, show them together ----
        errors = []
        if not name:
            errors.append("Name is required.")
        if "@" not in email:
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if role not in SELF_REGISTER_ROLES:
            errors.append("Please choose Provider or Recipient.")
        if email and User.query.filter_by(email=email).first():
            errors.append("That email is already registered.")

        capacity_people = None
        if role == "recipient":
            if capacity.isdigit() and int(capacity) > 0:
                capacity_people = int(capacity)
            else:
                errors.append(
                    "Recipients must enter how many people they can "
                    "serve (a number above 0).")

        if errors:
            for message in errors:
                flash(message, "danger")
            # `form` lets the template keep what the user already typed
            return render_template("auth/register.html", form=request.form)

        # ---- create the user ----
        user = User(
            name=name, email=email, role=role, phone=phone,
            address=address, latitude=latitude, longitude=longitude,
            capacity_people=capacity_people,
            # providers are trusted; recipients wait for admin approval
            is_verified=(role == "provider"),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if role == "recipient":
            flash("Registered! An admin must verify your organisation "
                  "before you can request food. You can log in now.",
                  "info")
        else:
            flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect_to_dashboard(current_user)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        # Same message for "no such user" and "wrong password" (security)
        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        login_user(user)
        flash(f"Welcome back, {user.name}!", "success")
        if user.role == "recipient" and not user.is_verified:
            flash("Your account is waiting for admin verification.",
                  "warning")

        next_page = request.args.get("next")
        if _is_safe_next(next_page):
            return redirect(next_page)
        return redirect_to_dashboard(user)

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))
