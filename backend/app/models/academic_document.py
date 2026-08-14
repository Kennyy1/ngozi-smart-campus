from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.graduation_record import GraduationRecord
    from app.models.institution import Institution
    from app.models.official_transcript import OfficialTranscript
    from app.models.programme import Programme
    from app.models.student import Student
    from app.models.user import User


class AcademicDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_documents"
    __table_args__ = (
        UniqueConstraint("document_reference", name="uq_academic_documents_reference"),
        UniqueConstraint("verification_code", name="uq_academic_documents_verification_code"),
        CheckConstraint("document_type IN ('certificate', 'statement_of_result')", name="academic_document_type"),
        CheckConstraint("status IN ('draft', 'issued', 'revoked', 'inactive')", name="academic_document_status"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    programme_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("programmes.id", ondelete="RESTRICT"), nullable=True, index=True)
    graduation_record_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("graduation_records.id", ondelete="RESTRICT"), nullable=True, index=True)
    official_transcript_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("official_transcripts.id", ondelete="RESTRICT"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    document_reference: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    verification_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by_user_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="academic_documents")
    student: Mapped[Student] = relationship(back_populates="academic_documents")
    programme: Mapped[Programme | None] = relationship(back_populates="academic_documents")
    graduation_record: Mapped[GraduationRecord | None] = relationship(back_populates="academic_documents")
    official_transcript: Mapped[OfficialTranscript | None] = relationship(back_populates="academic_documents")
    generated_by_user: Mapped[User] = relationship(foreign_keys=[generated_by_user_id])
    issued_by_user: Mapped[User | None] = relationship(foreign_keys=[issued_by_user_id])
    revoked_by_user: Mapped[User | None] = relationship(foreign_keys=[revoked_by_user_id])
