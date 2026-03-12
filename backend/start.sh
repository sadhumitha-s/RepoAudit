#!/bin/bash
set -e

# Start Celery worker in background
celery -A worker worker --loglevel=info --concurrency=2 --max-tasks-per-child=10 &

# Start FastAPI — Cloud Run sets $PORT, local dev defaults to 7860
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}"