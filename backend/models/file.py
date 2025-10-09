# models/file.py
from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import String, Text, Enum, ForeignKey, BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, GUID, JSONType, now_utc

ProcessingStatus = Enum('uploaded', 'processing', 'completed', 'failed', name='file_processing_status')


class File(Base):
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey('project.id', ondelete='CASCADE'), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    checksum: Mapped[Optional[str]] = mapped_column(String(64))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    uploaded_at: Mapped[Optional[str]] = mapped_column(default=now_utc)
    processing_status: Mapped[str] = mapped_column(ProcessingStatus, default='uploaded', nullable=False)
    metadata_: Mapped[dict] = mapped_column('metadata', JSONType(), default=dict)

    project = relationship('Project', back_populates='files')

    __table_args__ = (
        Index('ix_file_project_time', 'project_id', 'uploaded_at'),
        Index('ix_file_checksum', 'checksum', unique=False),
    )

    def to_dict(self) -> dict:
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'filename': self.filename,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'checksum': self.checksum,
            'uploaded_by': str(self.uploaded_by),
            'uploaded_at': self.uploaded_at.isoformat() if hasattr(self.uploaded_at, 'isoformat') else self.uploaded_at,
            'processing_status': self.processing_status,
            'metadata': self.metadata_,
        }