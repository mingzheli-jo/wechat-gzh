from celery import Celery  # type: ignore[import-untyped]

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "wechat_rewriter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.crawl",
        "app.tasks.rewrite",
        "app.tasks.review",
        "app.tasks.images",
        "app.tasks.publish",
        "app.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "app.tasks.crawl.*": {"queue": "crawl"},
        "app.tasks.rewrite.*": {"queue": "rewrite"},
        "app.tasks.review.*": {"queue": "review"},
        "app.tasks.images.*": {"queue": "publish"},
        "app.tasks.publish.*": {"queue": "publish"},
    },
    worker_concurrency=settings.celery_worker_concurrency,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
)
