"""Authentication: register, login, logout and email OTP verification.

The OTP part only runs when the env var OTP_ENABLED is "true".
With OTP off, register and login behave exactly as before.
"""
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.otp import (OTP_LIFETIME_MINUTES, attempts_left, issue_otp,
                          otp_enabled, send_otp_email, seconds_until_resend,
                          verify_otp)
from app.auth.utils import redirect_to_dashboard
from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Admin is NOT allowed here: admins are created by create_admin.py only
SELF_REGISTER_ROLES = ("provider", "recipient")

# Session key that remembers who is busy verifying their email
# (the person is NOT logged in yet)
OTP_SESSION_KEY = "otp_user_id"


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


# ------------------------------------------------------------------
# OTP helpers (private to this file)
# ------------------------------------------------------------------
def _mask_email(email):
    """'ravi@gmail.com' -> 'r***@gmail.com' (shown on the verify page)."""
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


def _send_new_code(user):
    """Create a fresh code, email it, and tell the user what happened."""
    code = issue_otp(user)
    sent = send_otp_email(user.email, user.name, code)
    if sent:
        flash(f"We sent a 6-digit code to {_mask_email(user.email)}. "
              f"It expires in {OTP_LIFETIME_MINUTES} minutes.", "info")
    else:
        # Demo mode: the code was printed in the server log instead
        flash("We could not send the email right now (demo mode). "
              "The code was written to the server log.", "warning")


def _begin_verification(user):
    """Remember the user in the session and make sure a code was sent."""
    session[OTP_SESSION_KEY] = user.id
    if user.email_otp is not None and seconds_until_resend(user) > 0:
        # A code went out a moment ago: do not spam, just ask for it
        flash("A code was sent a moment ago. Enter it below.", "info")
    else:
        _send_new_code(user)


def _pending_user():
    """The user who is verifying their email right now (or None)."""
    user_id = session.get(OTP_SESSION_KEY)
    if user_id is None:
        return None
    return db.session.get(User, user_id)


# ------------------------------------------------------------------
# Register / login / logout
# ------------------------------------------------------------------
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

        # ---- OTP ON: verify the email before the first login ----
        if otp_enabled():
            _begin_verification(user)
            return redirect(url_for("auth.verify"))

        # ---- OTP OFF: exactly the old behaviour ----
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

        # OTP ON: an unverified email cannot log in, it goes to verify
        if otp_enabled() and not user.email_verified:
            flash("Please verify your email before logging in.", "warning")
            _begin_verification(user)
            return redirect(url_for("auth.verify"))

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


# ------------------------------------------------------------------
# Email OTP: verify page and resend button
# ------------------------------------------------------------------
@bp.route("/verify", methods=["GET", "POST"])
def verify():
    if current_user.is_authenticated:
        return redirect_to_dashboard(current_user)
    if not otp_enabled():
        return redirect(url_for("auth.login"))

    user = _pending_user()
    if user is None:
        flash("Please register or log in first.", "warning")
        return redirect(url_for("auth.login"))
    if user.email_verified:
        session.pop(OTP_SESSION_KEY, None)
        flash("Your email is already verified. Please log in.", "success")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        ok, reason = verify_otp(user, request.form.get("code", ""))
        if ok:
            session.pop(OTP_SESSION_KEY, None)
            flash("Email verified! You can log in now.", "success")
            return redirect(url_for("auth.login"))

        if reason == "wrong":
            flash(f"Wrong code. You have {attempts_left(user)} "
                  "tries left.", "danger")
        elif reason == "locked":
            flash("Too many wrong tries. Click 'Resend code' to get a "
                  "new one.", "danger")
        elif reason == "expired":
            flash("That code has expired. Click 'Resend code'.", "danger")
        elif reason == "no_code":
            flash("No code found. Click 'Resend code'.", "danger")
        else:
            flash("Enter the 6-digit code from your email.", "danger")

    return render_template(
        "auth/verify.html",
        masked_email=_mask_email(user.email),
        wait_seconds=seconds_until_resend(user),
    )


@bp.route("/resend", methods=["POST"])
def resend():
    if current_user.is_authenticated:
        return redirect_to_dashboard(current_user)
    if not otp_enabled():
        return redirect(url_for("auth.login"))

    user = _pending_user()
    if user is None:
        flash("Please register or log in first.", "warning")
        return redirect(url_for("auth.login"))

    wait = seconds_until_resend(user)
    if wait > 0:
        flash(f"Please wait {wait} seconds before asking for a new code.",
              "warning")
    else:
        _send_new_code(user)
    return redirect(url_for("auth.verify"))
