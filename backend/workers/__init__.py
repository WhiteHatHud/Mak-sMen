"""
Workers package initialization.
Exports the Celery app instance for use by main application.
"""

from workers.analysis_worker import celery_app

__all__ = ["celery_app"]