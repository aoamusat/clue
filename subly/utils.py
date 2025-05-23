"""
Utility functions for Subly application.
"""

from functools import wraps
import os
from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from sqlalchemy import text
from subly.extensions import db
from subly.models import SubscriptionPlan, User
from subly.logger import get_logger

logger = get_logger()


def admin_required(fn):
    """
    Decorator to check if the user is an admin.
    If not, raises a 403 Forbidden error.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role", "user") != "admin":
            return (
                jsonify({"message": "You are not authorized to perform this action."}),
                403,
            )
        return fn(*args, **kwargs)

    return wrapper


def create_admin_user():
    """Create an admin user if it doesn't exist."""

    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            email="admin@subly.io",
            role="admin",
        )
        admin_user.set_password(os.environ.get("APP_ADMIN_PASSWORD", "admin12345"))
        db.session.add(admin_user)
        db.session.commit()
        logger.info("✅ Admin user created successfully.")
    else:
        logger.info("⚠️ Admin user already exists. No action taken.")


def init_subscription_plans():
    """Initialize default subscription plans if they don't exist."""

    # Check if plans already exist using raw SQL (more efficient)
    count_sql = text("SELECT COUNT(*) FROM subscription_plans")
    count = db.session.execute(count_sql).scalar()

    if count > 0:
        return

    # Default plans
    plans = [
        {
            "name": "Sandbox",
            "price": 0.00,
            "description": "Basic access with limited features",
            "features": "Access to basic content;500 API calls per day;No premium features",
        },
        {
            "name": "Startup",
            "price": 15.00,
            "description": "Standard access with more features",
            "features": "All Free features;1 Million API calls;Standard support",
        },
        {
            "name": "Pro",
            "price": 100.00,
            "description": "Full access with all features",
            "features": "All Startup features;Unlimited API calls;Standard support;Advanced analytics",
        },
        {
            "name": "Enterprise",
            "price": 300.00,
            "description": "Full access with all features",
            "features": "All Pro features;Unlimited API calls;Priority support;Advanced analytics;BYOC",
        },
    ]

    # Add default plans
    for plan_data in plans:
        plan = SubscriptionPlan(
            name=plan_data.get("name"),
            price=plan_data.get("price"),
            description=plan_data.get("description"),
            features=plan_data.get("features"),
        )
        db.session.add(plan)

    db.session.commit()


def analyze_query_performance(query_str, params=None):
    """
    Analyze SQL query performance using EXPLAIN
    Returns explanation of query execution plan
    """
    if params is None:
        params = {}

    # Only works with SQLite - for production with MySQL/PostgreSQL, adapt as needed
    explain_query = f"EXPLAIN QUERY PLAN {query_str}"

    try:
        result = db.session.execute(text(explain_query), params).fetchall()
        return result
    except Exception as e:
        return str(e)
