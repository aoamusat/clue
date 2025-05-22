"""
Unit tests for the Subly API
"""

import unittest
import json
import time
from datetime import datetime, timedelta, timezone

from subly import create_app, db
from subly.models import User, UserSubscription
from subly.utils import init_subscription_plans


class TestAPI(unittest.TestCase):
    """Unit tests for the Subly API"""

    def setUp(self):
        """Set up test environment"""
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "JWT_SECRET_KEY": "test-secret-key",
            }
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Create tables and initialize data
        db.create_all()
        init_subscription_plans()

        # Create test user
        self.test_user = User(username="testuser", email="test@example.com")
        self.test_user.set_password("password")
        db.session.add(self.test_user)
        db.session.commit()

        # Get login token
        response = self.client.post(
            "/api/auth/login", json={"username": "testuser", "password": "password"}
        )
        data = json.loads(response.data)
        self.token = data["access_token"]

    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_register_user(self):
        """Test user registration"""
        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password",
            },
        )
        self.assertEqual(response.status_code, 201)

        user = User.query.filter_by(username="newuser").first()
        self.assertIsNotNone(user)

    def test_login(self):
        """Test user login"""
        response = self.client.post(
            "/api/auth/login", json={"username": "testuser", "password": "password"}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("access_token", data)

    def test_get_subscription_plans(self):
        """Test getting subscription plans"""
        response = self.client.get("/api/subscriptions/plans")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 4)  # We created 3 default plans

        # Verify plans are sorted by price
        self.assertEqual(data[0]["name"], "Sandbox")
        self.assertEqual(data[1]["name"], "Startup")
        self.assertEqual(data[2]["name"], "Pro")
        self.assertEqual(data[3]["name"], "Enterprise")

    def test_subscribe_and_get_active(self):
        """Test subscribing to a plan and getting active subscription"""
        # Get plan ID
        response = self.client.get("/api/subscriptions/plans")
        plans = json.loads(response.data)
        pro_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Pro")

        # Subscribe to plan
        response = self.client.post(
            "/api/subscriptions/subscribe",
            json={"plan_id": pro_plan_id},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 201)

        # Check active subscription
        response = self.client.get(
            "/api/subscriptions/active",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)
        subscription = json.loads(response.data)
        self.assertEqual(subscription["plan_name"], "Pro")
        self.assertTrue(subscription["is_active"])

    def test_cancel_subscription(self):
        """Test cancelling a subscription"""
        # Get a plan ID
        response = self.client.get("/api/subscriptions/plans")
        plans = json.loads(response.data)
        basic_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Sandbox")

        # Subscribe to plan
        self.client.post(
            "/api/subscriptions/subscribe",
            json={"plan_id": basic_plan_id},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        # Cancel subscription
        response = self.client.post(
            "/api/subscriptions/cancel",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)

        # Check active subscription
        response = self.client.get(
            "/api/subscriptions/active",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 404)  # No active subscription

    def test_upgrade_subscription(self):
        """Test upgrading subscription"""
        # Get plan IDs
        response = self.client.get("/api/subscriptions/plans")
        plans = json.loads(response.data)
        basic_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Sandbox")
        pro_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Pro")

        # Subscribe to basic plan
        self.client.post(
            "/api/subscriptions/subscribe",
            json={"plan_id": basic_plan_id},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        # Upgrade to pro plan
        response = self.client.post(
            "/api/subscriptions/upgrade",
            json={"plan_id": pro_plan_id},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)

        # Check active subscription
        response = self.client.get(
            "/api/subscriptions/active",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        subscription = json.loads(response.data)
        self.assertEqual(subscription["plan_name"], "Pro")

    def test_subscription_history(self):
        """Test subscription history with multiple subscriptions"""
        # Get plan IDs
        response = self.client.get("/api/subscriptions/plans")
        plans = json.loads(response.data)
        basic_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Sandbox")
        pro_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Pro")

        # Create multiple subscriptions
        for i in range(5):
            # Alternate between plans
            plan_id = basic_plan_id if i % 2 == 0 else pro_plan_id

            # Create subscription with backdated start times
            subscription = UserSubscription(
                user_id=self.test_user.id,
                plan_id=plan_id,
                start_date=datetime.now(timezone.utc) - timedelta(days=30 * (5 - i)),
                end_date=(
                    datetime.now(timezone.utc) - timedelta(days=30 * (4 - i))
                    if i < 4
                    else None
                ),
                is_active=i == 4,  # Only the last one is active
            )
            db.session.add(subscription)

        db.session.commit()

        # Get subscription history
        response = self.client.get(
            "/api/subscriptions/history",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Check pagination and results
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["subscriptions"]), 5)

        # Check ordering (most recent first)
        self.assertTrue(data["subscriptions"][0]["is_active"])

    def test_performance_active_subscription(self):
        """Test performance of getting active subscription"""
        # Create subscription
        response = self.client.get("/api/subscriptions/plans")
        plans = json.loads(response.data)
        pro_plan_id = next(plan["id"] for plan in plans if plan["name"] == "Pro")

        self.client.post(
            "/api/subscriptions/subscribe",
            json={"plan_id": pro_plan_id},
            headers={"Authorization": f"Bearer {self.token}"},
        )

        # Measure performance of optimized query
        start_time = time.time()
        response = self.client.get(
            "/api/subscriptions/active",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        optimized_time = time.time() - start_time

        # Compare with non-optimized ORM query (direct database query)
        start_time = time.time()
        with self.app.app_context():
            subscription = (
                UserSubscription.query.filter_by(
                    user_id=self.test_user.id, is_active=True
                )
                .filter(
                    (UserSubscription.end_date == None)
                    | (UserSubscription.end_date > datetime.now(timezone.utc))
                )
                .first()
            )
        orm_time = time.time() - start_time

        # Print performance comparison
        print(f"\nPerformance comparison:")
        print(f"Optimized raw SQL query: {optimized_time:.6f} seconds")
        print(f"Standard ORM query: {orm_time:.6f} seconds")
        print(f"Optimization factor: {orm_time/optimized_time:.2f}x faster")

        self.assertEqual(response.status_code, 200)

    def test_performance_subscription_history(self):
        """Test performance of subscription history with a large dataset"""
        # Create test data - a large number of subscription records
        response = self.client.get("/api/subscriptions/plans")
        plans = json.loads(response.data)
        plan_ids = [plan["id"] for plan in plans]

        # Create 100 subscription records
        user_id = self.test_user.id
        for i in range(100):
            plan_id = plan_ids[i % len(plan_ids)]
            start_date = datetime.now(timezone.utc) - timedelta(days=i * 10)
            end_date = start_date + timedelta(days=30) if i > 0 else None

            subscription = UserSubscription(
                user_id=user_id,
                plan_id=plan_id,
                start_date=start_date,
                end_date=end_date,
                is_active=i == 0,  # Only the latest is active
            )
            db.session.add(subscription)

        db.session.commit()

        # Test optimized query performance
        start_time = time.time()
        response = self.client.get(
            "/api/subscriptions/history?page=1&per_page=10",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        optimized_time = time.time() - start_time

        # Test standard ORM query performance
        start_time = time.time()
        with self.app.app_context():
            query = UserSubscription.query.filter_by(user_id=user_id)
            total = query.count()
            subscriptions = (
                query.order_by(UserSubscription.created_at.desc())
                .limit(10)
                .offset(0)
                .all()
            )
        orm_time = time.time() - start_time

        # Print performance comparison
        print(f"\nSubscription History Performance:")
        print(f"Optimized raw SQL query: {optimized_time:.6f} seconds")
        print(f"Standard ORM query: {orm_time:.6f} seconds")
        print(f"Optimization factor: {orm_time/optimized_time:.2f}x faster")

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["total"], 100)
        self.assertEqual(len(data["subscriptions"]), 10)


if __name__ == "__main__":
    unittest.main()
