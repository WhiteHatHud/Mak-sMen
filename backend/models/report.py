# models/report.py
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import String, Text, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID, JSONType, now_utc

ReportFormat = Enum('pdf', 'html', 'json', name='report_format')


class Report(Base):
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('analysisresult.id', ondelete='CASCADE'), nullable=False, index=True)
    format: Mapped[str] = mapped_column(ReportFormat, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    generated_at: Mapped[Optional[str]] = mapped_column(default=now_utc)
    generated_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    is_flagged: Mapped[bool] = mapped_column(default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column('metadata', JSONType(), default=dict)

    analysis = relationship('AnalysisResult', back_populates='reports')

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'analysis_id': str(self.analysis_id),
            'format': self.format,
            'file_path': self.file_path,
            'generated_at': self.generated_at.isoformat() if hasattr(self.generated_at, 'isoformat') else self.generated_at,
            'generated_by': str(self.generated_by),
            'is_flagged': self.is_flagged,
            'flag_reason': self.flag_reason,
            'metadata': self.metadata_,
        }

    # --------- Async helpers for routes (stubs) ---------
    @classmethod
    async def get(cls, *, report_id: str | uuid.UUID, user_id: str | uuid.UUID):
        async for session in get_session():
            return await session.get(cls, uuid.UUID(str(report_id)))

    @classmethod
    async def list_by_project(cls, *, project_id: str | uuid.UUID, user_id: str | uuid.UUID):
        return []

    @classmethod
    async def flag(cls, *, report_id: str | uuid.UUID, user_id: str | uuid.UUID):
        async for session in get_session():
            obj = await session.get(cls, uuid.UUID(str(report_id)))
            if not obj:
                return False
            obj.is_flagged = True
            await session.commit()
            return True

    @classmethod
    async def stream_file(cls, *, report_id: str | uuid.UUID, user_id: str | uuid.UUID):
        # Streaming is handled in service layer; return None placeholder
        return None

