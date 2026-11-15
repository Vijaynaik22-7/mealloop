"""Local test only - do NOT commit this file."""
from jinja2 import ChoiceLoader, DictLoader
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User

# In-memory database, so your real mealloop.db is untouched
app = create_app({
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
})

# Stand-in base.html, used only if the real one doesn't exist yet
app.jinja_env.loader = ChoiceLoader([
    app.jinja_env.loader,
    DictLoader({
        "base.html": (
            "<html><head><title>{% block title %}{% endblock %}</title>"
            "</head><body>{% block content %}{% endblock %}</body></html>"
        )
    }),
])

with app.app_context():
    user = User(
        name="Test NGO",
        email="ngo@test.com",
        password_hash=generate_password_hash("pass1234"),
        role="recipient",
        address="12 MG Road",
        capacity_people=50,
        is_verified=False,
    )
    db.session.add(user)
    db.session.commit()
    uid = user.id

    client = app.test_client()
    # Pretend this user is logged in
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True

    r = client.get("/recipient/profile")
    print("GET profile:", r.status_code, "(expect 200)")
    print("Shows pending notice:", b"pending admin approval" in r.data)

    r = client.post("/recipient/profile", data={
        "name": "Helping Hands", "address": "5 Church St",
        "capacity_people": "80"})
    print("POST valid:", r.status_code, "(expect 302)")

    db.session.expire_all()
    saved = db.session.get(User, uid)
    print("Saved:", saved.name, saved.address, saved.capacity_people)

    r = client.post("/recipient/profile", data={
        "name": "", "address": "x", "capacity_people": "0"})
    print("POST invalid:", r.status_code, "(expect 400)")