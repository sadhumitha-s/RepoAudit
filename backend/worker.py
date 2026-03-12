import ssl
from celery import Celery
from config import get_settings

settings = get_settings()

celery_app = Celery(
    "repoaudit",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=10,
    task_soft_time_limit=120,
    task_time_limit=180,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# Enable TLS for Upstash Redis (rediss://) connections
if settings.celery_broker_url.startswith("rediss://"):
    celery_app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
        redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    )