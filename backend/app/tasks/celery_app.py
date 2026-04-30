from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "wechat_rewriter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.crawl",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "app.tasks.crawl.*": {"queue": "crawl"},
    },
    worker_concurrency=settings.celery_worker_concurrency,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
)
