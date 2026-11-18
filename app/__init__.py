"""MealLoop application factory."""
import importlib
import os

from flask import Flask, render_template

from app.extensions import db, login_manager

# Every module must expose a Blueprint named `bp` in its routes.py
BLUEPRINT_MODULES = [
    "app.auth.routes",
    "app.providers.routes",
    "app.recipients.routes",
    "app.admin.routes",
    "app.analytics.routes",
]


def register_blueprints(app):
    """Register each module's blueprint.

    If a teammate has not written their routes.py yet (file missing
    or no `bp` inside), we skip it so the app still runs.
    """
    for module_name in BLUEPRINT_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as err:
            # Only ignore "this module does not exist yet".
            # Real errors (e.g. a missing library) must still show up.
            missing = err.name or ""
            if module_name == missing or module_name.startswith(
                    missing + "."):
                print(f"[MealLoop] skipped {module_name} (not found)")
                continue
            raise
        bp = getattr(module, "bp", None)
        if bp is None:
            print(f"[MealLoop] skipped {module_name} (no `bp` yet)")
            continue
        app.register_blueprint(bp)


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        # Relative sqlite path is stored in the instance/ folder
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///mealloop.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Short commit id of this build (set in the Docker image by CI)
        BUILD_SHA=os.environ.get("BUILD_SHA", "dev")[:7],
    )
    if test_config:
        app.config.update(test_config)  # tests override settings here

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from app import models  # noqa: F401  (so tables are known)
        db.create_all()

    register_blueprints(app)

    @app.context_processor
    def inject_build_sha():
        """Make {{ build_sha }} available in every template (footer)."""
        return {"build_sha": app.config["BUILD_SHA"]}

    @app.route("/")
    def home():
        return render_template("home.html")  # created in step 5

    @app.route("/health")
    def health():
        """Tiny endpoint for CI tests and the Docker healthcheck."""
        return {"status": "ok"}

    @app.route("/version")
    def version():
        """Which commit is running? Used to prove a deploy happened."""
        return {"version": app.config["BUILD_SHA"]}

    return app
