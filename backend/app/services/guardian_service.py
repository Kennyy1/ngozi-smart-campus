from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.guardian import Guardian
from app.models.guardian_student import GuardianStudent
from app.models.student import Student
from app.models.user import User
from app.schemas.guardian import GuardianCreate, GuardianRead, GuardianStudentCreate, GuardianStudentRead, GuardianStudentUpdate, GuardianUpdate, RelationshipStatus
from app.services.role_assignment_service import GUARDIAN_ROLE, GUARDIAN_ROLE_DESCRIPTION, ensure_user_role


class GuardianNotFoundError(Exception): pass
class GuardianConflictError(Exception): pass
class GuardianRelationshipNotFoundError(Exception): pass
class GuardianRelationshipConflictError(Exception): pass
class GuardianReferenceNotFoundError(Exception): pass


def create_guardian(session: Session, *, institution_id: UUID, data: GuardianCreate) -> GuardianRead:
    if session.scalar(select(User.id).where(User.institution_id == institution_id, User.email == str(data.email))) is not None:
        raise GuardianConflictError()
    user=User(institution_id=institution_id,email=str(data.email),password_hash=hash_password(data.password),first_name=data.first_name,last_name=data.last_name,phone=data.phone,is_active=True,is_verified=False)
    guardian=Guardian(institution_id=institution_id,user=user,occupation=data.occupation,address=data.address,emergency_contact=data.emergency_contact,is_active=True)
    try:
        session.add_all([user,guardian]); session.flush()
        ensure_user_role(session,user=user,institution_id=institution_id,role_name=GUARDIAN_ROLE,role_description=GUARDIAN_ROLE_DESCRIPTION)
        session.commit(); session.refresh(guardian)
    except IntegrityError as error:
        session.rollback(); raise GuardianConflictError() from error
    return _guardian_read(guardian)

def list_guardians(session: Session, *, institution_id: UUID) -> list[GuardianRead]:
    items=session.scalars(select(Guardian).options(joinedload(Guardian.user)).where(Guardian.institution_id==institution_id,Guardian.is_active.is_(True)).order_by(Guardian.created_at.desc())).all()
    return [_guardian_read(x) for x in items]

def get_guardian_model(session: Session, *, institution_id: UUID, guardian_id: UUID) -> Guardian:
    item=session.scalar(select(Guardian).options(joinedload(Guardian.user)).where(Guardian.id==guardian_id,Guardian.institution_id==institution_id))
    if item is None: raise GuardianNotFoundError()
    return item

def get_guardian(session: Session, *, institution_id: UUID, guardian_id: UUID) -> GuardianRead:
    return _guardian_read(get_guardian_model(session,institution_id=institution_id,guardian_id=guardian_id))

def update_guardian(session: Session, *, institution_id: UUID, guardian_id: UUID, data: GuardianUpdate) -> GuardianRead:
    guardian=get_guardian_model(session,institution_id=institution_id,guardian_id=guardian_id); changes=data.model_dump(exclude_unset=True)
    email=changes.get("email")
    if email is not None and str(email)!=guardian.user.email and session.scalar(select(User.id).where(User.institution_id==institution_id,User.email==str(email))) is not None: raise GuardianConflictError()
    for field in ("email","first_name","last_name","phone"):
        if field in changes: setattr(guardian.user,field,str(changes[field]) if field=="email" else changes[field])
    for field in ("occupation","address","emergency_contact","is_active"):
        if field in changes: setattr(guardian,field,changes[field])
    if changes.get("is_active") is False: guardian.user.is_active=False
    try: session.commit(); session.refresh(guardian)
    except IntegrityError as error: session.rollback(); raise GuardianConflictError() from error
    return _guardian_read(guardian)

def delete_guardian(session: Session, *, institution_id: UUID, guardian_id: UUID) -> None:
    guardian=get_guardian_model(session,institution_id=institution_id,guardian_id=guardian_id)
    guardian.is_active=False; guardian.user.is_active=False; session.commit()

def create_relationship(session: Session, *, institution_id: UUID, data: GuardianStudentCreate) -> GuardianStudentRead:
    guardian=session.scalar(select(Guardian).where(Guardian.id==data.guardian_id,Guardian.institution_id==institution_id,Guardian.is_active.is_(True)))
    student=session.scalar(select(Student).where(Student.id==data.student_id,Student.institution_id==institution_id))
    if guardian is None or student is None: raise GuardianReferenceNotFoundError()
    duplicate=session.scalar(select(GuardianStudent.id).where(GuardianStudent.institution_id==institution_id,GuardianStudent.guardian_id==data.guardian_id,GuardianStudent.student_id==data.student_id,GuardianStudent.status!="revoked"))
    if duplicate is not None: raise GuardianRelationshipConflictError()
    item=GuardianStudent(institution_id=institution_id,status="pending",**data.model_dump())
    try: session.add(item); session.commit(); session.refresh(item)
    except IntegrityError as error: session.rollback(); raise GuardianRelationshipConflictError() from error
    return GuardianStudentRead.model_validate(item,from_attributes=True)

def list_relationships(session: Session, *, institution_id: UUID, guardian_id: UUID | None=None, student_id: UUID | None=None) -> list[GuardianStudentRead]:
    statement=select(GuardianStudent).where(GuardianStudent.institution_id==institution_id)
    if guardian_id: statement=statement.where(GuardianStudent.guardian_id==guardian_id)
    if student_id: statement=statement.where(GuardianStudent.student_id==student_id)
    return [GuardianStudentRead.model_validate(x,from_attributes=True) for x in session.scalars(statement.order_by(GuardianStudent.created_at.desc())).all()]

def get_relationship_model(session: Session, *, institution_id: UUID, relationship_id: UUID) -> GuardianStudent:
    item=session.scalar(select(GuardianStudent).where(GuardianStudent.id==relationship_id,GuardianStudent.institution_id==institution_id))
    if item is None: raise GuardianRelationshipNotFoundError()
    return item

def update_relationship(session: Session, *, institution_id: UUID, relationship_id: UUID, data: GuardianStudentUpdate) -> GuardianStudentRead:
    item=get_relationship_model(session,institution_id=institution_id,relationship_id=relationship_id)
    for field,value in data.model_dump(exclude_unset=True).items(): setattr(item,field,value.value if hasattr(value,"value") else value)
    session.commit(); session.refresh(item); return GuardianStudentRead.model_validate(item,from_attributes=True)

def transition_relationship(session: Session, *, institution_id: UUID, relationship_id: UUID, target: RelationshipStatus) -> GuardianStudentRead:
    item=get_relationship_model(session,institution_id=institution_id,relationship_id=relationship_id)
    allowed={"pending":{"verified","revoked"},"verified":{"suspended","revoked"},"suspended":{"verified","revoked"},"revoked":set()}
    if target.value not in allowed[item.status]: raise GuardianRelationshipConflictError()
    item.status=target.value; session.commit(); session.refresh(item)
    return GuardianStudentRead.model_validate(item,from_attributes=True)

def _guardian_read(item: Guardian) -> GuardianRead:
    return GuardianRead(id=item.id,institution_id=item.institution_id,user_id=item.user_id,email=item.user.email,first_name=item.user.first_name,last_name=item.user.last_name,phone=item.user.phone,occupation=item.occupation,address=item.address,emergency_contact=item.emergency_contact,is_active=item.is_active,created_at=item.created_at,updated_at=item.updated_at)
