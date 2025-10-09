# models/analysis_result.py
from __future__ import annotations
from typing import Optional, List, Dict, Any
import uuid
import os
import json

from sqlalchemy import String, Text, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID, JSONType, now_utc

StatusEnum = Enum('pending', 'processing', 'completed', 'failed', name='analysis_status')


class AnalysisResult(Base):
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('project.id', ondelete='CASCADE'), nullable=False, index=True)
    file_ids: Mapped[list[str]] = mapped_column(JSONType(), default=list)  # list of UUIDs as strings
    status: Mapped[str] = mapped_column(StatusEnum, default='pending', nullable=False)
    ai_endpoint: Mapped[Optional[str]] = mapped_column(String(255))
    llm_enabled: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[Optional[str]] = mapped_column(default=now_utc)
    completed_at: Mapped[Optional[str]] = mapped_column(default=None)
    anomaly_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    results: Mapped[dict] = mapped_column(JSONType(), default=dict)
    metrics: Mapped[dict] = mapped_column(JSONType(), default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    project = relationship('Project', back_populates='analyses')
    reports = relationship('Report', back_populates='analysis', cascade='all,delete-orphan')

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'file_ids': self.file_ids,
            'status': self.status,
            'ai_endpoint': self.ai_endpoint,
            'llm_enabled': self.llm_enabled,
            'started_at': self.started_at.isoformat() if hasattr(self.started_at, 'isoformat') else self.started_at,
            'completed_at': self.completed_at.isoformat() if hasattr(self.completed_at, 'isoformat') else self.completed_at,
            'anomaly_count': self.anomaly_count,
            'results': self.results,
            'metrics': self.metrics,
            'error_message': self.error_message,
        }


# Simple Redis-backed status facade (used by routes)
try:
    import redis  # type: ignore
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception:  # pragma: no cover
    _r = None


def _status_key(aid: str) -> str:
    return f"analysis:{aid}:status"

def _result_key(aid: str) -> str:
    return f"analysis:{aid}:result"


class AnalysisStatus:
    @staticmethod
    def get(*, analysis_id: str, user_id: str | int) -> Optional[Dict[str, Any]]:
        if _r is None:
            return None
        v = _r.get(_status_key(analysis_id))
        if not v:
            return None
        obj = json.loads(v)
        return {
            'id': analysis_id,
            'status': obj.get('status', 'pending'),
            'progress': obj.get('progress'),
            'started_at': obj.get('started_at'),
            'finished_at': obj.get('finished_at'),
        }

    @staticmethod
    def get_results(*, analysis_id: str, user_id: str | int) -> Optional[Dict[str, Any]]:
        if _r is None:
            return None
        v = _r.get(_result_key(analysis_id))
        return json.loads(v) if v else None

    @staticmethod
    def list_by_project(*, project_id: str | int, user_id: str | int) -> List[Dict[str, Any]]:
        # For brevity, return empty; production should query DB table of analyses by project
        return []

