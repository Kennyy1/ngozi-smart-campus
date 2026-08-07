from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment_component import AssessmentComponent
    from app.models.course_registration import CourseRegistration
    from app.models.institution import Institution
    from app.models.user import User


class AssessmentScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_scores"
    __table_args__ = (
        CheckConstraint("score >= 0", name="assessment_score_score"),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="assessment_score_status",
        ),
        Index(
            "uq_assessment_scores_active_component_registration",
            "assessment_component_id",
            "course_registration_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_component_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_components.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_registration_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_registrations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    graded_by_user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)

    institution: Mapped[Institution] = relationship(back_populates="assessment_scores")
    assessment_component: Mapped[AssessmentComponent] = relationship(back_populates="assessment_scores")
    course_registration: Mapped[CourseRegistration] = relationship(back_populates="assessment_scores")
    graded_by_user: Mapped[User] = relationship(back_populates="graded_assessment_scores")
