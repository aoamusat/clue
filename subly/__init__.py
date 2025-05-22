"""
Application factory for Subly.
This module contains the application factory function `create_app` that initializes
the Flask application, configures it, and registers blueprints.
"""

import os

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from dotenv import load_dotenv

# Import and register blueprints/routes
from subly.routes import auth_bp, subscription_bp

# Initialize subscription plans if they don't exist
from subly.utils import init_subscription_plans

# Import initialized SQLAlchemy & JWTManager instances
from subly.extensions import db, jwt

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

    # Initialize SQLAlchemy with app
    db.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(subscription_bp)

    # Create tables
    with app.app_context():
        db.create_all()
        init_subscription_plans()

    return app
