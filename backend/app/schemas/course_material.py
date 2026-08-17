from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


class CourseMaterialType(StrEnum):
    LECTURE_NOTE="lecture_note"; SLIDE="slide"; ASSIGNMENT_RESOURCE="assignment_resource"; READING="reading"; LINK="link"; OTHER="other"


class CourseMaterialCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    course_offering_id: UUID
    title: str=Field(min_length=1,max_length=255)
    description: str|None=None
    material_type: CourseMaterialType
    external_url: AnyHttpUrl

    @field_validator("title")
    @classmethod
    def title_clean(cls,value:str)->str:
        value=" ".join(value.split())
        if not value: raise ValueError("must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def description_clean(cls,value:str|None)->str|None:return None if value is None else value.strip() or None


class CourseMaterialUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title: str|None=Field(default=None,min_length=1,max_length=255)
    description: str|None=None
    material_type: CourseMaterialType|None=None
    external_url: AnyHttpUrl|None=None

    @field_validator("title","material_type","external_url")
    @classmethod
    def required_not_null(cls,value:object)->object:
        if value is None: raise ValueError("must not be null")
        return value


class CourseMaterialRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID; institution_id:UUID; course_offering_id:UUID; uploaded_by_user_id:UUID
    title:str; description:str|None; material_type:CourseMaterialType; external_url:str|None
    source_type:str; original_filename:str|None; mime_type:str|None; file_size:int|None
    is_published:bool; published_at:datetime|None; created_at:datetime; updated_at:datetime
