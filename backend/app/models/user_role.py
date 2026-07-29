from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.role import Role
    from app.models.user import User


class UserRole(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "role_id",
            "institution_id",
            name="uq_user_roles_user_role_institution",
        ),
    )

    user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="role_assignments")
    role: Mapped[Role] = relationship(back_populates="user_role_assignments")
    institution: Mapped[Institution] = relationship(
        back_populates="user_role_assignments",
    )
