from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.academic_document import AcademicDocument
    from app.models.institution import Institution
    from app.models.programme import Programme
    from app.models.student import Student
    from app.models.user import User


class GraduationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "graduation_records"
    __table_args__ = (
        UniqueConstraint("graduation_reference", name="uq_graduation_records_reference"),
        CheckConstraint("status IN ('draft', 'confirmed', 'revoked', 'inactive')", name="graduation_record_status"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    programme_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("programmes.id", ondelete="RESTRICT"), nullable=False, index=True)
    graduation_reference: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    award_title: Mapped[str] = mapped_column(String(300), nullable=False)
    degree_classification: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    degree_classification_label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    final_cgpa: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    academic_standing: Mapped[str] = mapped_column(String(50), nullable=False)
    eligibility_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    outcome_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prepared_by_user_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_student_enrollment_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    previous_student_graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="graduation_records")
    student: Mapped[Student] = relationship(back_populates="graduation_records")
    programme: Mapped[Programme] = relationship(back_populates="graduation_records")
    prepared_by_user: Mapped[User] = relationship(foreign_keys=[prepared_by_user_id])
    confirmed_by_user: Mapped[User | None] = relationship(foreign_keys=[confirmed_by_user_id])
    revoked_by_user: Mapped[User | None] = relationship(foreign_keys=[revoked_by_user_id])
    academic_documents: Mapped[list[AcademicDocument]] = relationship(back_populates="graduation_record")
