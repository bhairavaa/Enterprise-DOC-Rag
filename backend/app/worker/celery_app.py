from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("enterprise_doc_rag", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

# Ensures tasks register with this app when the worker starts
# (celery -A app.worker.celery_app worker).
import app.worker.tasks  # noqa: E402, F401
