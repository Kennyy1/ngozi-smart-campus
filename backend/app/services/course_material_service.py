from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course_material import CourseMaterial
from app.models.course_registration import CourseRegistration
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.student import Student
from app.schemas.course_material import CourseMaterialCreate, CourseMaterialUpdate
from app.services.course_material_storage import StoredMaterialFile, remove, resolve


class CourseMaterialNotFoundError(Exception):pass
class CourseMaterialUnauthorizedError(Exception):pass
class DuplicateCourseMaterialError(Exception):pass


def _lecturer_assignment(session:Session,*,institution_id:UUID,user_id:UUID,offering_id:UUID)->bool:
    return session.scalar(select(LecturerAssignment.id).join(Lecturer, LecturerAssignment.lecturer_id==Lecturer.id).where(
        LecturerAssignment.institution_id==institution_id, Lecturer.user_id==user_id,
        LecturerAssignment.course_offering_id==offering_id, LecturerAssignment.status=="active")) is not None


def _student_registration(session:Session,*,institution_id:UUID,user_id:UUID,offering_id:UUID)->bool:
    return session.scalar(select(CourseRegistration.id).join(Student,CourseRegistration.student_id==Student.id).where(
        CourseRegistration.institution_id==institution_id,Student.user_id==user_id,
        CourseRegistration.course_offering_id==offering_id,CourseRegistration.status=="active",
        CourseRegistration.registration_status=="registered")) is not None


def _get(session:Session,*,institution_id:UUID,material_id:UUID)->CourseMaterial:
    item=session.scalar(select(CourseMaterial).where(CourseMaterial.id==material_id,CourseMaterial.institution_id==institution_id))
    if item is None:raise CourseMaterialNotFoundError()
    return item


def _visible(session:Session,item:CourseMaterial,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],write:bool=False)->bool:
    if "lecturer" in roles and _lecturer_assignment(session,institution_id=institution_id,user_id=user_id,offering_id=item.course_offering_id):return True
    if not write and "student" in roles and item.is_published and _student_registration(session,institution_id=institution_id,user_id=user_id,offering_id=item.course_offering_id):return True
    if not write and ({"administrator","system_super_admin"}&set(roles)):return True
    return False


def create(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],data:CourseMaterialCreate)->CourseMaterial:
    if "lecturer" not in roles or not _lecturer_assignment(session,institution_id=institution_id,user_id=user_id,offering_id=data.course_offering_id):raise CourseMaterialNotFoundError()
    item=CourseMaterial(institution_id=institution_id,uploaded_by_user_id=user_id,file_reference=None,source_type="external_url",**data.model_dump(mode="json"))
    session.add(item)
    try:session.commit()
    except IntegrityError as error:session.rollback();raise DuplicateCourseMaterialError() from error
    session.refresh(item);return item


def create_uploaded(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],course_offering_id:UUID,title:str,description:str|None,material_type:str,stored:StoredMaterialFile)->CourseMaterial:
    if "lecturer" not in roles or not _lecturer_assignment(session,institution_id=institution_id,user_id=user_id,offering_id=course_offering_id):raise CourseMaterialNotFoundError()
    normalized=" ".join(title.split())
    if not normalized:raise ValueError("title must not be blank")
    item=CourseMaterial(institution_id=institution_id,course_offering_id=course_offering_id,uploaded_by_user_id=user_id,title=normalized,description=description.strip() or None if description else None,material_type=material_type,source_type="uploaded_file",file_reference=stored.reference,original_filename=stored.original_filename,mime_type=stored.mime_type,file_size=stored.size,external_url=None)
    session.add(item)
    try:session.commit()
    except IntegrityError as error:session.rollback();remove(stored.reference);raise DuplicateCourseMaterialError() from error
    session.refresh(item);return item


def list_items(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],course_offering_id:UUID|None=None)->list[CourseMaterial]:
    statement=select(CourseMaterial).where(CourseMaterial.institution_id==institution_id)
    if course_offering_id:statement=statement.where(CourseMaterial.course_offering_id==course_offering_id)
    items=list(session.scalars(statement.order_by(CourseMaterial.created_at.desc())).all())
    return [x for x in items if _visible(session,x,institution_id=institution_id,user_id=user_id,roles=roles)]


def get(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],material_id:UUID)->CourseMaterial:
    item=_get(session,institution_id=institution_id,material_id=material_id)
    if not _visible(session,item,institution_id=institution_id,user_id=user_id,roles=roles):raise CourseMaterialNotFoundError()
    return item


def update(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],material_id:UUID,data:CourseMaterialUpdate)->CourseMaterial:
    item=_get(session,institution_id=institution_id,material_id=material_id)
    if not _visible(session,item,institution_id=institution_id,user_id=user_id,roles=roles,write=True):raise CourseMaterialNotFoundError()
    for key,value in data.model_dump(exclude_unset=True,mode="json").items():setattr(item,key,value)
    try:session.commit()
    except IntegrityError as error:session.rollback();raise DuplicateCourseMaterialError() from error
    session.refresh(item);return item


def publish(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],material_id:UUID,value:bool)->CourseMaterial:
    item=_get(session,institution_id=institution_id,material_id=material_id)
    if not _visible(session,item,institution_id=institution_id,user_id=user_id,roles=roles,write=True):raise CourseMaterialNotFoundError()
    item.is_published=value;item.published_at=datetime.now(timezone.utc) if value else None;session.commit();session.refresh(item);return item


def delete(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],material_id:UUID)->None:
    item=_get(session,institution_id=institution_id,material_id=material_id)
    if not _visible(session,item,institution_id=institution_id,user_id=user_id,roles=roles,write=True):raise CourseMaterialNotFoundError()
    reference=item.file_reference;session.delete(item);session.commit();remove(reference)


def download(session:Session,*,institution_id:UUID,user_id:UUID,roles:tuple[str,...],material_id:UUID):
    item=get(session,institution_id=institution_id,user_id=user_id,roles=roles,material_id=material_id)
    if item.source_type!="uploaded_file" or not item.file_reference:raise CourseMaterialNotFoundError()
    return item,resolve(item.file_reference)
