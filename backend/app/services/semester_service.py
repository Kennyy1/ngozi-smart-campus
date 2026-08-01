from datetime import date
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_session import AcademicSession
from app.models.semester import Semester
from app.schemas.semester import SemesterCreate, SemesterStatus, SemesterUpdate


class SemesterNotFoundError(Exception): pass
class SemesterAcademicSessionNotFoundError(Exception): pass
class DuplicateSemesterNameError(Exception): pass
class DuplicateSemesterSequenceError(Exception): pass
class DuplicateSemesterError(Exception): pass
class InvalidSemesterDateRangeError(Exception): pass
class SemesterOutsideAcademicSessionError(Exception): pass
class InactiveCurrentAcademicSessionError(Exception): pass


def create_semester(session: Session, *, institution_id: UUID, semester_data: SemesterCreate) -> Semester:
    parent = _resolve_academic_session(session, academic_session_id=semester_data.academic_session_id, institution_id=institution_id)
    _ensure_name_available(session, academic_session_id=parent.id, name=semester_data.name)
    _ensure_sequence_available(session, academic_session_id=parent.id, sequence_number=semester_data.sequence_number)
    _validate_dates(start_date=semester_data.start_date, end_date=semester_data.end_date, parent=parent)
    if semester_data.is_current:
        _validate_current_parent(parent)
        _unset_current_semester(session, institution_id=institution_id)
    semester = Semester(institution_id=institution_id, **semester_data.model_dump())
    session.add(semester)
    _commit(session)
    session.refresh(semester)
    return semester


def list_semesters(session: Session, *, institution_id: UUID, academic_session_id: UUID | None = None, status: SemesterStatus | None = None, is_current: bool | None = None) -> list[Semester]:
    statement = select(Semester).where(Semester.institution_id == institution_id)
    if academic_session_id is not None:
        statement = statement.where(Semester.academic_session_id == academic_session_id)
    if status is not None:
        statement = statement.where(Semester.status == status)
    if is_current is not None:
        statement = statement.where(Semester.is_current == is_current)
    return list(session.scalars(statement.order_by(Semester.start_date.desc(), Semester.sequence_number, Semester.id)).all())


def get_semester(session: Session, *, semester_id: UUID, institution_id: UUID) -> Semester:
    semester = session.scalar(select(Semester).where(Semester.id == semester_id, Semester.institution_id == institution_id))
    if semester is None:
        raise SemesterNotFoundError()
    return semester


def get_current_semester(session: Session, *, institution_id: UUID) -> Semester:
    semester = session.scalar(select(Semester).where(Semester.institution_id == institution_id, Semester.is_current.is_(True)))
    if semester is None:
        raise SemesterNotFoundError()
    return semester


def update_semester(session: Session, *, semester_id: UUID, institution_id: UUID, semester_data: SemesterUpdate) -> Semester:
    semester = get_semester(session, semester_id=semester_id, institution_id=institution_id)
    changes = semester_data.model_dump(exclude_unset=True)
    parent_id = changes.get("academic_session_id", semester.academic_session_id)
    parent = _resolve_academic_session(session, academic_session_id=parent_id, institution_id=institution_id)
    name = changes.get("name", semester.name)
    sequence = changes.get("sequence_number", semester.sequence_number)
    if parent_id != semester.academic_session_id or name != semester.name:
        _ensure_name_available(session, academic_session_id=parent_id, name=name, exclude_id=semester.id)
    if parent_id != semester.academic_session_id or sequence != semester.sequence_number:
        _ensure_sequence_available(session, academic_session_id=parent_id, sequence_number=sequence, exclude_id=semester.id)
    start_date = changes.get("start_date", semester.start_date)
    end_date = changes.get("end_date", semester.end_date)
    _validate_dates(start_date=start_date, end_date=end_date, parent=parent)
    will_be_current = changes.get("is_current", semester.is_current)
    if will_be_current:
        _validate_current_parent(parent)
    if changes.get("is_current") is True and not semester.is_current:
        _unset_current_semester(session, institution_id=institution_id, exclude_id=semester.id)
    for field, value in changes.items():
        setattr(semester, field, value)
    _commit(session)
    session.refresh(semester)
    return semester


def delete_semester(session: Session, *, semester_id: UUID, institution_id: UUID) -> None:
    semester = get_semester(session, semester_id=semester_id, institution_id=institution_id)
    semester.is_current = False
    session.delete(semester)
    _commit(session)


def _resolve_academic_session(session: Session, *, academic_session_id: UUID, institution_id: UUID) -> AcademicSession:
    parent = session.scalar(select(AcademicSession).where(AcademicSession.id == academic_session_id, AcademicSession.institution_id == institution_id))
    if parent is None:
        raise SemesterAcademicSessionNotFoundError()
    return parent


def _validate_dates(*, start_date: date, end_date: date, parent: AcademicSession) -> None:
    if start_date >= end_date:
        raise InvalidSemesterDateRangeError()
    if start_date < parent.start_date or end_date > parent.end_date:
        raise SemesterOutsideAcademicSessionError()


def _ensure_name_available(session: Session, *, academic_session_id: UUID, name: str, exclude_id: UUID | None = None) -> None:
    statement = select(Semester.id).where(Semester.academic_session_id == academic_session_id, Semester.name == name)
    if exclude_id is not None:
        statement = statement.where(Semester.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateSemesterNameError()


def _ensure_sequence_available(session: Session, *, academic_session_id: UUID, sequence_number: int, exclude_id: UUID | None = None) -> None:
    statement = select(Semester.id).where(Semester.academic_session_id == academic_session_id, Semester.sequence_number == sequence_number)
    if exclude_id is not None:
        statement = statement.where(Semester.id != exclude_id)
    if session.scalar(statement) is not None:
        raise DuplicateSemesterSequenceError()


def _validate_current_parent(parent: AcademicSession) -> None:
    if not parent.is_current:
        raise InactiveCurrentAcademicSessionError()


def _unset_current_semester(session: Session, *, institution_id: UUID, exclude_id: UUID | None = None) -> None:
    statement = update(Semester).where(Semester.institution_id == institution_id, Semester.is_current.is_(True)).values(is_current=False)
    if exclude_id is not None:
        statement = statement.where(Semester.id != exclude_id)
    session.execute(statement)


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateSemesterError() from error
