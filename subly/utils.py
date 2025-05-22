"""
Utility functions for Subly application.
"""

from sqlalchemy import text
from subly import db
from subly.models import SubscriptionPlan


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
