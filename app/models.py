"""ALL database models for MealLoop (shared by every module)."""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # 'provider' | 'recipient' | 'admin'
    role = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    # Only used for recipients (how many people they can feed)
    capacity_people = db.Column(db.Integer)
    # providers: auto True, recipients: False until admin approves
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    # True once the user proved they own the email address (OTP feature).
    # Only checked at login when OTP_ENABLED is "true".
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Hash the password; we never store plain text."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class EmailOtp(db.Model):
    """One-time code for email verification (one row per user).

    The code itself is never stored, only its hash. Sending a new code
    replaces the old row's values.
    """
    __tablename__ = "email_otp"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    # Wrong guesses so far (the code is locked after 5)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    # Used to enforce "resend only after 60 seconds"
    last_sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship(
        "User",
        backref=db.backref("email_otp", uselist=False,
                           cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<EmailOtp user={self.user_id} attempts={self.attempts}>"


class Donation(db.Model):
    __tablename__ = "donation"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False)
    food_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    prepared_at = db.Column(db.DateTime)
    expiry_time = db.Column(db.DateTime, nullable=False)
    pickup_location = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    # 'available'|'requested'|'accepted'|'collected'|'expired'|'cancelled'
    status = db.Column(db.String(20), default="available", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship("User", backref="donations")
    requests = db.relationship("DonationRequest", backref="donation")

    def __repr__(self):
        return f"<Donation {self.id} {self.food_name} [{self.status}]>"


class DonationRequest(db.Model):
    __tablename__ = "donation_request"

    id = db.Column(db.Integer, primary_key=True)
    donation_id = db.Column(
        db.Integer, db.ForeignKey("donation.id"), nullable=False)
    recipient_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False)
    people_to_serve = db.Column(db.Integer, nullable=False)
    # 'pending' | 'accepted' | 'rejected' | 'collected'
    status = db.Column(db.String(20), default="pending", nullable=False)
    priority_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    collected_at = db.Column(db.DateTime, nullable=True)

    recipient = db.relationship("User", backref="requests")

    def __repr__(self):
        return f"<DonationRequest {self.id} [{self.status}]>"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this to get the logged-in user from the session."""
    return db.session.get(User, int(user_id))
