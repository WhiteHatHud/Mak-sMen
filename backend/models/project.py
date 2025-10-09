# models/project.py
from __future__ import annotations
from typing import Optional, List, Tuple
import uuid

from sqlalchemy import Column, String, Text, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from .base import Base, GUID, JSONType, now_utc, get_session


ProjectStatus = Enum('active', 'archived', 'deleted', name='project_status')


class Project(Base):
    """Projects table.
    NOTE: Column named "metadata" conflicts with SQLAlchemy's Base.metadata. Use attribute name `metadata_` mapped to DB column 'metadata'.
    """
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    created_at: Mapped[Optional[str]] = mapped_column(default=now_utc)
    updated_at: Mapped[Optional[str]] = mapped_column(default=now_utc, onupdate=now_utc)
    deleted_at: Mapped[Optional[str]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(ProjectStatus, default='active', nullable=False)
    metadata_: Mapped[dict] = mapped_column('metadata', JSONType(), default=dict)

    # Relationships
    files = relationship('File', back_populates='project', cascade='all,delete-orphan')
    analyses = relationship('AnalysisResult', back_populates='project', cascade='all,delete-orphan')
    webhooks = relationship('Webhook', back_populates='project', cascade='all,delete-orphan')

    __table_args__ = (
        Index('ix_project_active_name', 'name', postgresql_where=(status == 'active')),
    )

    # --------- Serialization ---------
    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'created_by': str(self.created_by),
            'created_at': self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            'updated_at': self.updated_at.isoformat() if hasattr(self.updated_at, 'isoformat') else self.updated_at,
            'deleted_at': self.deleted_at.isoformat() if hasattr(self.deleted_at, 'isoformat') else self.deleted_at,
            'status': self.status,
            'metadata': self.metadata_,
        }

    # --------- CRUD (async helpers used by routes) ---------
    @classmethod
    async def create(cls, *, name: str, description: Optional[str], owner_id: str | uuid.UUID) -> 'Project':
        async for session in get_session():
            obj = cls(name=name, description=description, created_by=uuid.UUID(str(owner_id)))
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    @classmethod
    async def list_paginated(cls, *, owner_id: str | uuid.UUID, page: int, size: int) -> Tuple[List['Project'], int]:
        async for session in get_session():
            q = select(cls).where(cls.created_by == uuid.UUID(str(owner_id)), cls.status != 'deleted').order_by(cls.created_at.desc())
            total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
            items = (await session.execute(q.limit(size).offset((page-1)*size))).scalars().all()
            return items, total

    @classmethod
    async def get(cls, project_id: str | uuid.UUID, *, owner_id: str | uuid.UUID) -> Optional['Project']:
        async for session in get_session():
            return await session.get(cls, uuid.UUID(str(project_id)))

    @classmethod
    async def update(cls, project_id: str | uuid.UUID, **fields) -> 'Project':
        async for session in get_session():
            obj = await session.get(cls, uuid.UUID(str(project_id)))
            if not obj:
                raise ValueError('Project not found')
            for k, v in fields.items():
                if k == 'metadata':
                    setattr(obj, 'metadata_', v)
                elif hasattr(obj, k):
                    setattr(obj, k, v)
            await session.commit()
            await session.refresh(obj)
            return obj

    @classmethod
    async def soft_delete(cls, project_id: str | uuid.UUID) -> None:
        async for session in get_session():
            obj = await session.get(cls, uuid.UUID(str(project_id)))
            if not obj:
                return
            obj.deleted_at = now_utc()
            obj.status = 'deleted'
            await session.commit()