# models/webhook.py
from __future__ import annotations
from typing import Optional, List
import uuid

from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID, JSONType, now_utc


class Webhook(Base):
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('project.id', ondelete='CASCADE'), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[List[str]] = mapped_column(JSONType(), default=list)  # array of event types
    secret: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[str]] = mapped_column(default=now_utc)
    last_triggered: Mapped[Optional[str]] = mapped_column(default=None)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship('Project', back_populates='webhooks')

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'url': self.url,
            'events': self.events,
            'secret': '***' if self.secret else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            'last_triggered': self.last_triggered.isoformat() if hasattr(self.last_triggered, 'isoformat') else self.last_triggered,
            'failure_count': self.failure_count,
        }

    # Async helpers (stubs)
    @classmethod
    async def create(cls, *, user_id: str | uuid.UUID, url: str, secret: Optional[str], event: str, active: bool):
        async for session in get_session():
            obj = cls(project_id=uuid.UUID(int=0), url=url, events=[event], secret=secret, is_active=active)  # TODO: map user->project
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    @classmethod
    async def list(cls, *, user_id: str | uuid.UUID):
        return []

    @classmethod
    async def update(cls, *, webhook_id: str | uuid.UUID, user_id: str | uuid.UUID, **fields):
        return None

    @classmethod
    async def delete(cls, *, webhook_id: str | uuid.UUID, user_id: str | uuid.UUID):
        return False

    @classmethod
    async def test_fire(cls, *, webhook_id: str | uuid.UUID, user_id: str | uuid.UUID):
        return None
