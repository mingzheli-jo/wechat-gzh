"""Crawl tasks live here. Real task body lands in Task 2.7."""
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.crawl.crawl_library_item")  # type: ignore[misc]
def crawl_library_item(item_id: str) -> None:
    """Crawl + parse a library item. Body filled in Task 2.7."""
