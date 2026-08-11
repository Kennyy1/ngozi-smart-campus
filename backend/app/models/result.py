from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course_offering import CourseOffering
    from app.models.course_registration import CourseRegistration
    from app.models.institution import Institution
    from app.models.student import Student
    from app.models.user import User


class Result(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "results"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'published', 'withheld', 'inactive')", name="result_status"),
        Index("uq_results_active_course_registration", "course_registration_id", unique=True, postgresql_where=text("status != 'inactive'")),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    course_registration_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_registrations.id", ondelete="RESTRICT"), nullable=False, index=True)
    course_offering_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    continuous_assessment_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    examination_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    final_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    grade_letter: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    grade_point: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    computed_by_user_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    submitted_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    approved_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    published_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="results")
    course_registration: Mapped[CourseRegistration] = relationship(back_populates="results")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="results")
    student: Mapped[Student] = relationship(back_populates="results")
    computed_by_user: Mapped[User] = relationship(foreign_keys=[computed_by_user_id])
    submitted_by_user: Mapped[User | None] = relationship(foreign_keys=[submitted_by_user_id])
    approved_by_user: Mapped[User | None] = relationship(foreign_keys=[approved_by_user_id])
    published_by_user: Mapped[User | None] = relationship(foreign_keys=[published_by_user_id])
