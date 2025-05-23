# Subly: A Subscription Management API

A RESTful API using Flask and SQLAlchemy for managing user subscriptions with a focus on SQL query optimization and performance.

## Features

- User registration and authentication using JWT
- Subscription plan management
- User subscription management (subscribe, upgrade, cancel)
- Optimized SQL queries for handling subscriptions at scale
- Performance testing and comparison of optimized vs standard queries

## Optimization Techniques

This API implements several SQL optimization techniques:

### 1. Strategic Indexing

- Composite indexes for commonly filtered fields (e.g., `idx_user_active` on `user_id` and `is_active`)
- Indexes on frequently joined or filtered columns to improve lookup speed
- Date range indexes for subscription period queries

### 2. Raw SQL Queries

- Custom SQL queries for performance-critical operations instead of relying solely on ORM
- Optimized JOIN operations to retrieve data in a single query
- Careful selection of columns to avoid unnecessary data transfer

### 3. Pagination

- Efficient pagination using LIMIT and OFFSET with proper indexing
- Separate count queries to optimize page calculation

### 4. Query Analysis

- Included tools for analyzing query performance and execution plans
- Performance comparison tests between standard ORM and optimized queries

## Setup Instructions

### Using Docker

1. Build the Docker image:
   ```
   docker build -f Dockerfile -t getclue/subly:latest . 
   ```
2. Run the container image
   ```
   docker run -p 5020:5000 --env FLASK_APP=subly --env FLASK_ENV=development --env JWT_ACCESS_TOKEN_EXPIRES=3600 --env JWT_SECRET_KEY=secret --env APP_ADMIN_PASSWORD=admin12345 --env SQLALCHEMY_DATABASE_URI=mysql+pymysql://username:password@db_host/db_name --env DEBUG=0 getclue/subly:latest
   ```
3. The API will be available at `http://localhost:5020`

### Alternatively Using Virtual Environment

1. Create a virtual environment:
   ```
   python -m venv .venv
   ```

2. Activate the virtual environment:
   - On Windows: `.venv\Scripts\activate`
   - On Unix/MacOS: `source .venv/bin/activate`

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Setup environment variables: See the sample `.env.example` file.
5. Run database migration & seeding
   ```
   flask db upgrade
   flask db-seed
   ```

6. Run the application:
   ```
   flask --app subly run --debug
   ```

7. The API will be available at `http://localhost:5000`

## Running Tests

Run the test suite:
```
python -m pytest tests/*
```

To run performance tests specifically:
```
python -m pytest tests/test_api.py
```

## API Endpoints

### Authentication

- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Authenticate and get JWT token

### Subscription Plans

- `GET /api/subscriptions/plans` - List all subscription plans
- `POST /api/subscriptions/plans` - Create a new subscription plan (admin)

### User Subscriptions

- `POST /api/subscriptions/subscribe` - Subscribe to a plan
- `GET /api/subscriptions/active` - Get active subscription
- `GET /api/subscriptions/history` - Get subscription history
- `POST /api/subscriptions/cancel` - Cancel active subscription
- `POST /api/subscriptions/upgrade` - Upgrade/change subscription

## Query Optimization Details

### Optimized Active Subscription Query

Standard ORM query:
```python
subscription = UserSubscription.query.filter_by(
    user_id=user_id,
    is_active=True
).filter(
    (UserSubscription.end_date == None) | 
    (UserSubscription.end_date > datetime.now(timezone.utc))
).first()
```

Optimized raw SQL query:
```sql
SELECT us.*, sp.name as plan_name, sp.price as plan_price
FROM user_subscriptions us
JOIN subscription_plans sp ON us.plan_id = sp.id
WHERE us.user_id = :user_id 
AND us.is_active = 1 
AND (us.end_date IS NULL OR us.end_date > :current_date)
LIMIT 1
```

Benefits:
- Single query for subscription and plan details
- Uses composite index on user_id and is_active
- LIMIT 1 ensures early termination

### Optimized Subscription History Query

Standard ORM approach:
```python
query = UserSubscription.query.filter_by(user_id=user_id)
total = query.count()
subscriptions = query.order_by(UserSubscription.created_at.desc()).limit(per_page).offset(offset).all()
```

Optimized raw SQL query:
```sql
SELECT us.*, sp.name as plan_name, sp.price as plan_price
FROM user_subscriptions us
JOIN subscription_plans sp ON us.plan_id = sp.id
WHERE us.user_id = :user_id
ORDER BY us.created_at DESC
LIMIT :per_page OFFSET :offset
```

With a separate count query:
```sql
SELECT COUNT(*) as total FROM user_subscriptions WHERE user_id = :user_id
```

Benefits:
- Removes the need for separate join queries
- Avoids counting all rows when only a page worth of data is needed
- Uses index on user_id

Performance improvements in tests show these optimizations provide 2-5x speed improvements on moderate-sized datasets, with benefits increasing as the database grows.