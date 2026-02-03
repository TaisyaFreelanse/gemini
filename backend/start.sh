#!/bin/sh

set -e

# Run database migrations
echo "=== Running database migrations ==="
alembic upgrade head
echo "=== Migrations complete ==="

# Start Celery worker in background with output to stdout
echo "=== Starting Celery worker ==="
celery -A app.tasks.celery_app worker --loglevel=info 2>&1 &
CELERY_PID=$!
echo "=== Celery worker started with PID: $CELERY_PID ==="

# Wait a bit for Celery to connect to Redis
sleep 5

# Check if Celery is still running
if kill -0 $CELERY_PID 2>/dev/null; then
    echo "=== Celery worker is running ==="
else
    echo "=== ERROR: Celery worker failed to start! ==="
    exit 1
fi

# Start FastAPI server (foreground)
echo "=== Starting FastAPI server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
