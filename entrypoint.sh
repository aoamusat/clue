#!/bin/sh

echo "🔄 Running database migrations..."
flask db upgrade

echo "🌱 Initializing database tables..."
flask db-seed

echo "🚀 Starting app with Gunicorn..."
exec gunicorn --bind 0.0.0.0:5020 main:app
