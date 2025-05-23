"""
This file contains the route blueprints for user authentication and subscription management.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from sqlalchemy import text

from subly.extensions import db
from subly.models import User, SubscriptionPlan, UserSubscription
from subly.schemas import (
    LoginSchema,
    RegisterSchema,
    SubscriptionPlanSchema,
    CreatePlanSchema,
)
from subly.logger import get_logger
from subly.utils import admin_required

logger = get_logger()

# Create route blueprints
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
subscription_bp = Blueprint("subscription", __name__, url_prefix="/api/subscriptions")


# Authentication routes
@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user"""
    try:
        data = request.get_json()

        # Validate input data
        schema = RegisterSchema()
        errors = schema.validate(data)

        if errors:
            return jsonify({"errors": errors}), 400

        # Check if user already exists
        if User.query.filter_by(username=data["username"]).first():
            return jsonify({"error": "Username already exists"}), 409

        if User.query.filter_by(email=data["email"]).first():
            return jsonify({"error": "Email already exists"}), 409

        # Create new user
        user = User(username=data["username"], email=data["email"])
        user.set_password(data["password"])

        db.session.add(user)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Registration successful!",
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                }
            ),
            201,
        )
    except Exception as e:
        logger.error("Database error during registration: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate a user"""
    try:
        data = request.get_json()
        # Validate input data
        schema = LoginSchema()
        errors = schema.validate(data)
        if errors:
            return jsonify({"errors": errors}), 400

        # Find user by username
        user = User.query.filter_by(username=data["username"]).first()

        if not user or not user.check_password(data["password"]):
            return jsonify({"error": "Invalid username or password"}), 401

        # Create access token
        access_token = create_access_token(
            identity=str(user.id), additional_claims={"role": user.role}
        )

        return (
            jsonify(
                {
                    "message": "Login successful",
                    "access_token": access_token,
                    "user_id": user.id,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error("Database error during login: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# Subscription routes
@subscription_bp.route("/plans", methods=["GET"])
def get_plans():
    """Get all subscription plans"""
    # Using optimized raw SQL for listing plans
    try:
        sql = text(
            """
            SELECT id, name, price, description, features
            FROM subscription_plans
            ORDER BY price ASC
        """
        )

        plans = db.session.execute(sql).fetchall()

        result = [
            {
                "id": plan.id,
                "name": plan.name,
                "price": plan.price,
                "description": plan.description,
                "features": plan.features,
            }
            for plan in plans
        ]
        return jsonify(result), 200
    except Exception as e:
        logger.error("Database error fetching plans: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@subscription_bp.route("/plans", methods=["POST"])
@jwt_required()
@admin_required
def create_plan():
    """Create a new subscription plan (admin only)"""
    # In a real app, you would add admin checks here
    try:
        data = request.get_json()

        # Validate input data
        schema = CreatePlanSchema()
        errors = schema.validate(data)

        if errors:
            return jsonify({"errors": errors}), 400
        # Check if plan already exists
        if SubscriptionPlan.query.filter_by(name=data["name"]).first():
            return jsonify({"error": "Plan with this name already exists"}), 409

        # Create new plan
        plan = SubscriptionPlan(
            name=data.get("name"),
            price=data.get("price"),
            description=data.get("description", ""),
            features=data.get("features", ""),
        )

        db.session.add(plan)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Plan created successfully",
                    "plan_id": plan.id,
                    "name": plan.name,
                    "price": plan.price,
                }
            ),
            201,
        )
    except Exception as e:
        logger.error("Database error creating plan: %s", e)
        return jsonify({"error": "Plan with this name already exists"}), 409


@subscription_bp.route("/subscribe", methods=["POST"])
@jwt_required()
def subscribe():
    """Subscribe a user to a plan"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()

        # Validate input data
        schema = SubscriptionPlanSchema()
        errors = schema.validate(data)
        if errors:
            return jsonify({"errors": errors}), 400

        plan_id = data.get("plan_id")

        # Check if plan exists
        plan = SubscriptionPlan.query.get(plan_id)
        if not plan:
            return jsonify({"error": "Invalid plan"}), 404

        active_sub = UserSubscription.get_active_subscription(user_id)
        if active_sub is not None:
            return (
                jsonify(
                    {
                        "message": "You have an active subscription",
                        "plan_name": active_sub.plan_name,
                        "expires": active_sub.end_date,
                    }
                ),
                400,
            )

        # Check if user has active subscription and cancel it
        UserSubscription.cancel_active_subscription(user_id)

        # Create new subscription
        duration = data.get("duration", 1)  # Duration in months, default 1
        end_date = datetime.now(timezone.utc) + timedelta(days=30 * duration)

        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            start_date=datetime.now(timezone.utc),
            end_date=end_date,
            is_active=True,
        )

        db.session.add(subscription)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Subscription successful",
                    "subscription_id": subscription.id,
                    "plan": plan.name,
                    "end_date": end_date.isoformat(),
                }
            ),
            201,
        )
    except Exception as e:
        logger.error("Error subscribing user: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@subscription_bp.route("/active", methods=["GET"])
@jwt_required()
def get_active_subscription():
    """Get user's active subscription"""
    try:
        user_id = int(get_jwt_identity())

        # Use optimized method
        subscription = UserSubscription.get_active_subscription(user_id)

        if not subscription:
            return jsonify({"message": "No active subscription found"}), 404

        return (
            jsonify(
                {
                    "subscription_id": subscription.id,
                    "plan_id": subscription.plan_id,
                    "plan_name": subscription.plan_name,
                    "plan_price": subscription.plan_price,
                    "start_date": subscription.start_date,
                    "end_date": (
                        subscription.end_date if subscription.end_date else None
                    ),
                    "is_active": bool(subscription.is_active),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error("Error fetching active subscription: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@subscription_bp.route("/history", methods=["GET"])
@jwt_required()
def get_subscription_history():
    """Get user's subscription history with pagination"""
    try:
        user_id = int(get_jwt_identity())
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        # Use optimized method with pagination
        subscriptions, total = UserSubscription.get_subscription_history(
            user_id, page, per_page
        )

        result = [
            {
                "subscription_id": sub.id,
                "plan_id": sub.plan_id,
                "plan_name": sub.plan_name,
                "plan_price": sub.plan_price,
                "start_date": sub.start_date,
                "end_date": sub.end_date if sub.end_date else None,
                "is_active": bool(sub.is_active),
            }
            for sub in subscriptions
        ]

        return (
            jsonify(
                {
                    "subscriptions": result,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error("Error fetching subscription history: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@subscription_bp.route("/cancel", methods=["POST"])
@jwt_required()
def cancel_subscription():
    """Cancel user's active subscription"""
    try:
        user_id = int(get_jwt_identity())

        # Use optimized method
        success = UserSubscription.cancel_active_subscription(user_id)

        if not success:
            return jsonify({"message": "No active subscription found"}), 404

        return jsonify({"message": "Subscription cancelled successfully"}), 200
    except Exception as e:
        logger.error("Error cancelling subscription: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@subscription_bp.route("/upgrade", methods=["POST"])
@jwt_required()
def upgrade_subscription():
    """Upgrade/change user's subscription"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()

        if not data or not data.get("plan_id"):
            return jsonify({"error": "Missing plan_id"}), 400

        plan_id = data["plan_id"]

        # Check if plan exists
        plan = SubscriptionPlan.query.get(plan_id)
        if not plan:
            return jsonify({"error": "Invalid plan"}), 404

        # Check if user has active subscription
        subscription = UserSubscription.get_active_subscription(user_id)

        if not subscription:
            # If no active subscription, create a new one
            return subscribe()

        # If it's the same plan, return error
        if subscription.plan_id == plan_id:
            return jsonify({"error": "Already subscribed to this plan"}), 400

        # Cancel current subscription
        UserSubscription.cancel_active_subscription(user_id)

        # Create new subscription
        duration = data.get("duration", 1)  # Duration in months, default 1
        end_date = datetime.now(timezone.utc) + timedelta(days=30 * duration)

        new_subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            start_date=datetime.now(timezone.utc),
            end_date=end_date,
            is_active=True,
        )

        db.session.add(new_subscription)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Subscription upgraded successfully",
                    "subscription_id": new_subscription.id,
                    "plan": plan.name,
                    "end_date": end_date.isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error("Error upgrading subscription: %s", e)
        return jsonify({"error": "Internal server error"}), 500
