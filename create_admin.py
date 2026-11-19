"""Create (or reset the password of) the admin account.

Usage (run from the project root, venv active):
    python create_admin.py --email admin@mealloop.com --password admin123
"""
import argparse
from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import User


def main():
    parser = argparse.ArgumentParser(description="Create a MealLoop admin")
    parser.add_argument("--name", default="MealLoop Admin")
    parser.add_argument("--email")
    parser.add_argument("--password")
    args = parser.parse_args()

    # Ask only for what was not given on the command line
    email = (args.email or input("Admin email: ")).strip().lower()
    password = args.password or getpass("Admin password: ")

    # Basic checks
    if "@" not in email:
        print("Error: enter a valid email address.")
        return 1
    if len(password) < 6:
        print("Error: password must be at least 6 characters.")
        return 1

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if user is not None and user.role != "admin":
            # Never turn a normal account into an admin by accident
            print(f"Error: {email} already exists as a {user.role}.")
            return 1

        if user is not None:
            # Already an admin: reset the password and make sure the
            # email counts as verified (needed when OTP_ENABLED=true)
            user.set_password(password)
            user.email_verified = True
            db.session.commit()
            print(f"Admin {email} already existed. Password updated.")
            return 0

        admin = User(
            name=args.name,
            email=email,
            role="admin",
            is_verified=True,   # admins are always verified
            email_verified=True,  # script users skip the email OTP
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin created: {email}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
