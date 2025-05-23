"""
models.py
This module contains the SQLAlchemy models for the Subly application.
"""

import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index, text
from sqlalchemy.ext.hybrid import hybrid_property

from subly.extensions import db


class User(db.Model):
    """
    User model representing a user in the system.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime, default=datetime.datetime.now(datetime.timezone.utc)
    )
    role = db.Column(db.String(20), default="user")  # e.g., user, admin, etc.

    # Create indexes for username/email for faster lookups
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_username", "username"),
    )

    def set_password(self, new_password):
        """Hash the password before storing it"""
        self.password = generate_password_hash(new_password)

    def check_password(self, password_to_check):
        """Check the hashed password against the provided password"""
        return check_password_hash(self.password, password_to_check)

    def __repr__(self):
        """String representation of the User model"""
        return f"<User {self.username}>"


class SubscriptionPlan(db.Model):
    """SubscriptionPlan model representing different subscription plans available."""

    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    features = db.Column(db.Text, nullable=True)

    def __repr__(self):
        """String representation of the SubscriptionPlan model"""
        return f"<SubscriptionPlan {self.name}>"


class UserSubscription(db.Model):
    """UserSubscription model representing a user's subscription to a plan."""

    __tablename__ = "user_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(
        db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False
    )
    start_date = db.Column(
        db.DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    end_date = db.Column(db.DateTime, nullable=True)  # Null means active/ongoing
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=datetime.datetime.now(datetime.timezone.utc)
    )

    # Relationships
    user = db.relationship("User", backref=db.backref("subscriptions", lazy="dynamic"))
    plan = db.relationship("SubscriptionPlan")

    # Create indexes for optimization
    __table_args__ = (
        # Composite index for finding active subscriptions for a user quickly
        Index("idx_user_active", "user_id", "is_active"),
        # Index for date-range queries
        Index("idx_subscription_dates", "start_date", "end_date"),
    )

    @hybrid_property
    def is_expired(self):
        """Check if the subscription is expired"""
        if not self.end_date:
            return False
        return self.end_date < datetime.datetime.now(datetime.timezone.utc)

    @classmethod
    def get_active_subscription(cls, user_id):
        """
        Optimized raw SQL query to get active subscription for a user.
        This is more efficient than the default ORM query for large datasets.
        """
        sql = text(
            """
            SELECT us.*, sp.name as plan_name, sp.price as plan_price
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.user_id = :user_id 
            AND us.is_active = 1 
            AND (us.end_date IS NULL OR us.end_date > :current_date)
            LIMIT 1
        """
        )

        result = db.session.execute(
            sql,
            {
                "user_id": user_id,
                "current_date": datetime.datetime.now(datetime.timezone.utc),
            },
        ).fetchone()

        return result

    @classmethod
    def get_subscription_history(cls, user_id, page=1, per_page=10):
        """
        Optimized query for subscription history with pagination.
        """
        offset = (page - 1) * per_page

        sql = text(
            """
            SELECT us.*, sp.name as plan_name, sp.price as plan_price
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.user_id = :user_id
            ORDER BY us.created_at DESC
            LIMIT :per_page OFFSET :offset
        """
        )

        results = db.session.execute(
            sql, {"user_id": user_id, "per_page": per_page, "offset": offset}
        ).fetchall()

        # Count total for pagination
        count_sql = text(
            """
            SELECT COUNT(*) as total
            FROM user_subscriptions
            WHERE user_id = :user_id
        """
        )

        total = db.session.execute(count_sql, {"user_id": user_id}).scalar()

        return results, total

    @classmethod
    def cancel_active_subscription(cls, user_id):
        """
        Optimized query to cancel a user's active subscription.
        Using direct SQL UPDATE for better performance on large datasets.
        """
        now = datetime.datetime.now(datetime.timezone.utc)

        sql = text(
            """
            UPDATE user_subscriptions
            SET is_active = 0, end_date = :now
            WHERE user_id = :user_id
            AND is_active = 1
            AND (end_date IS NULL OR end_date > :now)
        """
        )

        result = db.session.execute(sql, {"user_id": user_id, "now": now})
        db.session.commit()

        return result.rowcount > 0
