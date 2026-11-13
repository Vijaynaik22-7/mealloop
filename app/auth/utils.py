"""Shared helpers for role-based access (used by ALL modules)."""
from functools import wraps

from flask import current_app, flash, redirect
from flask_login import current_user

# Where each role lands after login
ROLE_HOME = {
    "provider": "/provider/dashboard",
    "recipient": "/recipient/dashboard",
    "admin": "/admin/dashboard",
}


def dashboard_url(user):
    """URL of the dashboard that belongs to this user's role."""
    return ROLE_HOME.get(user.role, "/")


def redirect_to_dashboard(user):
    return redirect(dashboard_url(user))


def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`.

    - Not logged in  -> sent to the login page
    - Wrong role     -> flash message + sent to their own dashboard
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(dashboard_url(current_user))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def verified_required(view):
    """Block users that the admin has not verified yet.

    Use it BELOW @role_required, on actions only (e.g. requesting food).
    Do NOT put it on the dashboard itself, or an unverified recipient
    would be redirected in a loop.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_verified:
            flash("Your account is not verified yet.", "warning")
            return redirect(dashboard_url(current_user))
        return view(*args, **kwargs)
    return wrapped