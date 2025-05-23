"""
Application factory for Subly.
This module contains the application factory function `create_app` that initializes
the Flask application, configures it, and registers blueprints.
"""

import os
from flask import Flask
from dotenv import load_dotenv

# Import and register blueprints/routes
from subly.routes import auth_bp, subscription_bp

# Initialize subscription plans if they don't exist
from subly.utils import create_admin_user, init_subscription_plans

# Import initialized SQLAlchemy & JWTManager instances
from subly.extensions import db, jwt, migrate

load_dotenv()


def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "SQLALCHEMY_DATABASE_URI",
            "sqlite:///" + os.path.join(app.instance_path, "subscription.sqlite"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "secret"),
        JWT_ACCESS_TOKEN_EXPIRES=3600,  # 1 hour
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize app with extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(subscription_bp)

    # Seed subscription plans table
    @app.cli.command("db-seed")
    def seed_database():
        """Seed the database with initial data."""
        try:
            init_subscription_plans()
            create_admin_user()
            app.logger.info("✅ Database seeded with initial data.")
        except Exception as e:
            app.logger.error("❌ Failed to initialize subscription plans: %s", e)

    return app
