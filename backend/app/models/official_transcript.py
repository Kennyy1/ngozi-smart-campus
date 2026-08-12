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
    from app.models.institution import Institution
    from app.models.programme import Programme
    from app.models.student import Student
    from app.models.user import User


class OfficialTranscript(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "official_transcripts"
    __table_args__ = (
        UniqueConstraint("institution_id", "transcript_reference", name="uq_official_transcripts_institution_reference"),
        CheckConstraint("status IN ('draft', 'issued', 'revoked', 'inactive')", name="official_transcript_status"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    programme_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("programmes.id", ondelete="RESTRICT"), nullable=False, index=True)
    transcript_reference: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by_user_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="official_transcripts")
    student: Mapped[Student] = relationship(back_populates="official_transcripts")
    programme: Mapped[Programme] = relationship(back_populates="official_transcripts")
    generated_by_user: Mapped[User] = relationship(foreign_keys=[generated_by_user_id])
    issued_by_user: Mapped[User | None] = relationship(foreign_keys=[issued_by_user_id])
    revoked_by_user: Mapped[User | None] = relationship(foreign_keys=[revoked_by_user_id])
