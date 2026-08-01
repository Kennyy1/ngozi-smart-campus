from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.institution import Institution
    from app.models.programme import Programme


class AcademicLevel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academic_levels"
    __table_args__ = (
        UniqueConstraint("programme_id", "name", name="uq_academic_levels_programme_name"),
        UniqueConstraint("programme_id", "code", name="uq_academic_levels_programme_code"),
        UniqueConstraint("programme_id", "sequence_number", name="uq_academic_levels_programme_sequence"),
        CheckConstraint("sequence_number > 0", name="academic_level_sequence_number"),
        CheckConstraint("status IN ('active', 'inactive')", name="academic_level_status"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    programme_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("programmes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    institution: Mapped[Institution] = relationship(back_populates="academic_levels")
    programme: Mapped[Programme] = relationship(back_populates="academic_levels")
    courses: Mapped[list[Course]] = relationship(back_populates="academic_level")
