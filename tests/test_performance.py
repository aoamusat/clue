import unittest
import time
import random
from subly import create_app, db
from subly.models import User, SubscriptionPlan, UserSubscription
from subly.utils import init_subscription_plans
from datetime import datetime, timedelta
from sqlalchemy import text


class TestQueryPerformance(unittest.TestCase):
    """Test class specifically for measuring and analyzing query performance."""

    def setUp(self):
        """Set up test environment with large dataset"""
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Create tables and initialize data
        db.create_all()
        init_subscription_plans()

        # Create large test dataset
        self._create_test_data()

    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _create_test_data(self):
        """Create a large dataset for performance testing"""
        # Create users
        self.user_count = 100
        self.users = []
        for i in range(self.user_count):
            user = User(username=f"user{i}", email=f"user{i}@example.com")
            user.set_password("password")
            db.session.add(user)
            self.users.append(user)

        db.session.commit()

        # Get subscription plans
        self.plans = SubscriptionPlan.query.all()

        # Create subscriptions - multiple per user with history
        self.subscription_count = 5000  # Total subscriptions across all users

        # Commit in batches to prevent memory issues
        batch_size = 500
        for i in range(0, self.subscription_count, batch_size):
            for j in range(i, min(i + batch_size, self.subscription_count)):
                user = self.users[j % self.user_count]
                plan = random.choice(self.plans)

                # Create subscription with random dates
                days_ago = random.randint(0, 365)
                duration = random.randint(28, 365)

                start_date = datetime.utcnow() - timedelta(days=days_ago)
                end_date = start_date + timedelta(days=duration)

                # Only make recent subscriptions active
                is_active = days_ago < duration

                subscription = UserSubscription(
                    user_id=user.id,
                    plan_id=plan.id,
                    start_date=start_date,
                    end_date=(
                        end_date if random.random() > 0.2 else None
                    ),  # Some have no end date
                    is_active=is_active,
                )
                db.session.add(subscription)

            # Commit the batch
            db.session.commit()

        print(
            f"Created {self.user_count} users and {self.subscription_count} subscriptions"
        )

    def test_active_subscription_performance(self):
        """Test performance of getting active subscription with optimized vs standard queries"""
        user_id = random.choice(self.users).id

        # Measure optimized raw SQL query
        start_time = time.time()
        for _ in range(100):  # Run multiple times for better measurement
            subscription = UserSubscription.get_active_subscription(user_id)
        optimized_time = (time.time() - start_time) / 100

        # Measure standard ORM query
        start_time = time.time()
        for _ in range(100):
            subscription = (
                UserSubscription.query.filter_by(user_id=user_id, is_active=True)
                .filter(
                    (UserSubscription.end_date == None)
                    | (UserSubscription.end_date > datetime.utcnow())
                )
                .first()
            )
        orm_time = (time.time() - start_time) / 100

        print(f"\nActive Subscription Query Performance:")
        print(
            f"Dataset: {self.user_count} users, {self.subscription_count} subscriptions"
        )
        print(f"Optimized raw SQL query: {optimized_time:.6f} seconds")
        print(f"Standard ORM query: {orm_time:.6f} seconds")
        print(f"Performance improvement: {(orm_time/optimized_time):.2f}x faster")

        # We should see at least some improvement
        self.assertLess(optimized_time, orm_time)

    def test_subscription_history_performance(self):
        """Test performance of subscription history with optimized vs standard queries"""
        user_id = random.choice(self.users).id
        page = 1
        per_page = 10

        # Measure optimized raw SQL query
        start_time = time.time()
        for _ in range(50):
            subscriptions, total = UserSubscription.get_subscription_history(
                user_id, page, per_page
            )
        optimized_time = (time.time() - start_time) / 50

        # Measure standard ORM query
        start_time = time.time()
        for _ in range(50):
            query = UserSubscription.query.filter_by(user_id=user_id)
            total = query.count()
            subscriptions = (
                query.order_by(UserSubscription.created_at.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
                .all()
            )
        orm_time = (time.time() - start_time) / 50

        print(f"\nSubscription History Query Performance:")
        print(
            f"Dataset: {self.user_count} users, {self.subscription_count} subscriptions"
        )
        print(f"Optimized raw SQL query: {optimized_time:.6f} seconds")
        print(f"Standard ORM query: {orm_time:.6f} seconds")
        print(f"Performance improvement: {(orm_time/optimized_time):.2f}x faster")

        # We should see at least some improvement
        self.assertLess(optimized_time, orm_time)

    def test_cancel_subscription_performance(self):
        """Test performance of cancelling subscriptions with optimized vs standard updates"""
        # Create a user with an active subscription for testing
        test_user = User(username="cancel_test", email="cancel@example.com")
        test_user.set_password("password")
        db.session.add(test_user)
        db.session.commit()

        plan = self.plans[0]
        subscription = UserSubscription(
            user_id=test_user.id,
            plan_id=plan.id,
            start_date=datetime.utcnow() - timedelta(days=10),
            end_date=datetime.utcnow() + timedelta(days=20),
            is_active=True,
        )
        db.session.add(subscription)
        db.session.commit()

        # Measure optimized raw SQL update
        start_time = time.time()
        for _ in range(10):
            # Reset subscription state
            subscription.is_active = True
            subscription.end_date = datetime.utcnow() + timedelta(days=20)
            db.session.commit()

            # Cancel using optimized method
            UserSubscription.cancel_active_subscription(test_user.id)
        optimized_time = (time.time() - start_time) / 10

        # Measure standard ORM update
        start_time = time.time()
        for _ in range(10):
            # Reset subscription state
            subscription.is_active = True
            subscription.end_date = datetime.utcnow() + timedelta(days=20)
            db.session.commit()

            # Cancel using standard ORM approach
            active_sub = (
                UserSubscription.query.filter_by(user_id=test_user.id, is_active=True)
                .filter(
                    (UserSubscription.end_date == None)
                    | (UserSubscription.end_date > datetime.utcnow())
                )
                .first()
            )

            if active_sub:
                active_sub.is_active = False
                active_sub.end_date = datetime.utcnow()
                db.session.commit()
        orm_time = (time.time() - start_time) / 10

        print(f"\nCancel Subscription Performance:")
        print(f"Optimized raw SQL update: {optimized_time:.6f} seconds")
        print(f"Standard ORM update: {orm_time:.6f} seconds")
        print(f"Performance improvement: {(orm_time/optimized_time):.2f}x faster")

        # We should see at least some improvement
        self.assertLess(optimized_time, orm_time)

    def test_query_plans(self):
        """Analyze query execution plans for optimized queries"""
        # This is most useful with MySQL/PostgreSQL - SQLite's EXPLAIN is limited
        # But this gives an idea of what to look for in production

        user_id = self.users[0].id

        # For active subscription query
        active_sql = """
            SELECT us.*, sp.name as plan_name, sp.price as plan_price
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.user_id = :user_id 
            AND us.is_active = 1 
            AND (us.end_date IS NULL OR us.end_date > :current_date)
            LIMIT 1
        """

        explain_result = db.session.execute(
            text(f"EXPLAIN QUERY PLAN {active_sql}"),
            {"user_id": user_id, "current_date": datetime.utcnow()},
        ).fetchall()

        print("\nQuery Execution Plan for Active Subscription:")
        for row in explain_result:
            print(f"- {row}")

        # For subscription history query
        history_sql = """
            SELECT us.*, sp.name as plan_name, sp.price as plan_price
            FROM user_subscriptions us
            JOIN subscription_plans sp ON us.plan_id = sp.id
            WHERE us.user_id = :user_id
            ORDER BY us.created_at DESC
            LIMIT :per_page OFFSET :offset
        """

        explain_result = db.session.execute(
            text(f"EXPLAIN QUERY PLAN {history_sql}"),
            {"user_id": user_id, "per_page": 10, "offset": 0},
        ).fetchall()

        print("\nQuery Execution Plan for Subscription History:")
        for row in explain_result:
            print(f"- {row}")


if __name__ == "__main__":
    unittest.main()
