from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AnnouncementType(StrEnum):
    GENERAL="general"; ACADEMIC="academic"; EXAMINATION="examination"; TIMETABLE="timetable"; EVENT="event"; EMERGENCY="emergency"; ADMINISTRATIVE="administrative"; COURSE="course"
class AudienceType(StrEnum):
    ALL="all"; STUDENTS="students"; LECTURERS="lecturers"; GUARDIANS="guardians"; ADMINISTRATORS="administrators"; PROGRAMME="programme"; ACADEMIC_LEVEL="academic_level"; COURSE_OFFERING="course_offering"
class Priority(StrEnum): NORMAL="normal"; IMPORTANT="important"; URGENT="urgent"
class AnnouncementStatus(StrEnum): DRAFT="draft"; PUBLISHED="published"; ARCHIVED="archived"

class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1,max_length=255); body: str = Field(min_length=1)
    announcement_type: AnnouncementType = AnnouncementType.GENERAL
    audience_type: AudienceType = AudienceType.ALL
    priority: Priority = Priority.NORMAL
    expires_at: datetime|None=None
    target_ids: list[UUID] = Field(default_factory=list,max_length=100)
    @field_validator("title","body")
    @classmethod
    def clean(cls,v:str)->str:
        v=v.strip()
        if not v: raise ValueError("must not be blank")
        return v
    @model_validator(mode="after")
    def targets(self):
        targeted=self.audience_type in {AudienceType.PROGRAMME,AudienceType.ACADEMIC_LEVEL,AudienceType.COURSE_OFFERING}
        if targeted != bool(self.target_ids): raise ValueError("target_ids are required only for targeted audiences")
        if len(set(self.target_ids)) != len(self.target_ids): raise ValueError("duplicate target_ids")
        return self

class AnnouncementUpdate(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=255); body:str|None=Field(default=None,min_length=1)
    announcement_type:AnnouncementType|None=None; audience_type:AudienceType|None=None; priority:Priority|None=None
    expires_at:datetime|None=None; target_ids:list[UUID]|None=Field(default=None,max_length=100)

class AnnouncementReadModel(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID; title:str; body:str; announcement_type:AnnouncementType; audience_type:AudienceType
    status:AnnouncementStatus; priority:Priority; published_at:datetime|None; expires_at:datetime|None
    created_at:datetime; updated_at:datetime; is_read:bool=False; target_labels:list[str]=Field(default_factory=list)

class CourseAnnouncementCreate(BaseModel):
    title:str=Field(min_length=1,max_length=255); body:str=Field(min_length=1); priority:Priority=Priority.NORMAL; expires_at:datetime|None=None

class NotificationReadModel(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID; notification_type:str; title:str; message:str; reference_type:str|None; reference_id:UUID|None; is_read:bool; read_at:datetime|None; created_at:datetime

class UnreadCount(BaseModel): unread_count:int

class TimetableItem(BaseModel):
    id:UUID; course_code:str; course_title:str; date:date; start_time:time; end_time:time; venue:str|None; session_type:str; status:str; topic:str
