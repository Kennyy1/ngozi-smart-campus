from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.semester import Semester


class AcademicSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_sessions"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "name",
            name="uq_academic_sessions_institution_name",
        ),
        CheckConstraint(
            "start_date < end_date",
            name="academic_session_date_range",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="academic_session_status",
        ),
        Index(
            "uq_academic_sessions_current_institution",
            "institution_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(
        back_populates="academic_sessions",
    )
    semesters: Mapped[list[Semester]] = relationship(back_populates="academic_session")
