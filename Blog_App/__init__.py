from .celery import app as celery_app

# Makes sure Celery app is always imported when Django starts
__all__ = ('celery_app',)
