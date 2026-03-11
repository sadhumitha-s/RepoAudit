FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends redis-server git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/repoaudit_clones

EXPOSE 7860

CMD redis-server --daemonize yes --maxmemory 128mb --maxmemory-policy allkeys-lru && \
    celery -A worker worker --loglevel=info --concurrency=2 --max-tasks-per-child=10 & \
    uvicorn main:app --host 0.0.0.0 --port 7860