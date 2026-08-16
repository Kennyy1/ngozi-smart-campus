from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.guardian_student import GuardianStudent
    from app.models.institution import Institution
    from app.models.user import User


class Guardian(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "guardians"
    __table_args__ = (UniqueConstraint("user_id", name="uq_guardians_user_id"),)

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        index=True,
    )

    institution: Mapped[Institution] = relationship(back_populates="guardians")
    user: Mapped[User] = relationship(back_populates="guardian_profile")
    student_relationships: Mapped[list[GuardianStudent]] = relationship(back_populates="guardian")
