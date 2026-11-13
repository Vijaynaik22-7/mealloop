"""Application factory. Every blueprint gets registered in create_app()."""
import os

from flask import Flask, jsonify

from app.extensions import db, login_manager


def create_app(test_config=None):
    app = Flask(__name__)

    # Default configuration (SECRET_KEY should come from the environment in production)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///mealloop.db"  # stored in the instance/ folder
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Tests pass their own config (e.g. an in-memory database)
    if test_config:
        app.config.update(test_config)

    # Make sure the instance/ folder exists (SQLite file lives there)
    os.makedirs(app.instance_path, exist_ok=True)

    # Connect extensions to this app
    db.init_app(app)
    login_manager.init_app(app)

    # ---- Register blueprints here as each member finishes theirs ----
    # from app.auth import bp as auth_bp
    # app.register_blueprint(auth_bp)
    # (same pattern for providers, recipients, admin, matching, analytics)

    @app.route("/health")
    def health():
        """Used by Docker healthcheck, CI and the deploy host."""
        return jsonify({"status": "ok"})

    return app
