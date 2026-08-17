from datetime import datetime
from uuid import UUID as UUIDType
from sqlalchemy import Boolean,CheckConstraint,DateTime,ForeignKey,Index,Integer,String,Text,UniqueConstraint,false,text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base
from app.models.mixins import TimestampMixin,UUIDPrimaryKeyMixin

class MobileAppRelease(UUIDPrimaryKeyMixin,TimestampMixin,Base):
    __tablename__="mobile_app_releases"
    __table_args__=(UniqueConstraint("platform","version",name="uq_mobile_app_releases_platform_version"),UniqueConstraint("platform","version_code",name="uq_mobile_app_releases_platform_version_code"),CheckConstraint("platform IN ('android')",name="mobile_app_release_platform"),CheckConstraint("status IN ('draft','published','retired')",name="mobile_app_release_status"),CheckConstraint("version_code > 0",name="mobile_app_release_version_code"),CheckConstraint("file_size > 0",name="mobile_app_release_file_size"),Index("uq_mobile_app_releases_latest_platform","platform",unique=True,postgresql_where=text("is_latest IS TRUE")))
    platform:Mapped[str]=mapped_column(String(20),nullable=False,index=True)
    version:Mapped[str]=mapped_column(String(40),nullable=False)
    version_code:Mapped[int]=mapped_column(Integer,nullable=False)
    filename:Mapped[str]=mapped_column(String(255),nullable=False)
    file_reference:Mapped[str]=mapped_column(String(255),nullable=False,unique=True)
    file_size:Mapped[int]=mapped_column(Integer,nullable=False)
    sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    release_notes:Mapped[str]=mapped_column(Text,nullable=False,default="",server_default="")
    status:Mapped[str]=mapped_column(String(20),nullable=False,default="draft",server_default="draft",index=True)
    is_latest:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False,server_default=false(),index=True)
    released_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_by_user_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False,index=True)
