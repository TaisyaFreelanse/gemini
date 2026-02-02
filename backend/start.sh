#!/bin/sh

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A app.tasks.celery_app worker --loglevel=info &

# Wait a bit for Celery to start
sleep 3

# Start FastAPI server
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
