from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.attendance_record import AttendanceRecord
from app.models.class_session import ClassSession
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.student import Student
from app.schemas.attendance_analytics import (
    AttendanceRiskItem,
    AttendanceRiskListResponse,
    ClassSessionAttendanceSummary,
    CourseOfferingAttendanceSummary,
    CourseRegistrationAttendanceSummary,
)


DEFAULT_MINIMUM_PERCENTAGE = 75.0
ATTENDANCE_STATUSES = ("present", "late", "absent", "excused")


class AttendanceAnalyticsRegistrationNotFoundError(Exception): pass
class AttendanceAnalyticsClassSessionNotFoundError(Exception): pass
class AttendanceAnalyticsCourseOfferingNotFoundError(Exception): pass
class InvalidMinimumPercentageError(Exception): pass


def get_course_registration_attendance_summary(
    session: Session,
    *,
    institution_id: UUID,
    course_registration_id: UUID,
    minimum_percentage: float = DEFAULT_MINIMUM_PERCENTAGE,
) -> CourseRegistrationAttendanceSummary:
    _validate_minimum_percentage(minimum_percentage)
    registration = _resolve_course_registration(session, course_registration_id=course_registration_id, institution_id=institution_id)
    eligible_sessions = _query_eligible_completed_sessions(session, institution_id=institution_id, course_offering_ids=[registration.course_offering_id])
    records = _query_active_attendance_records(
        session,
        institution_id=institution_id,
        class_session_ids=[item.id for item in eligible_sessions],
        course_registration_ids=[registration.id],
    )
    return _build_registration_summary(registration, eligible_sessions, records, minimum_percentage)


def get_class_session_attendance_summary(
    session: Session,
    *,
    institution_id: UUID,
    class_session_id: UUID,
) -> ClassSessionAttendanceSummary:
    class_session = _resolve_class_session(session, class_session_id=class_session_id, institution_id=institution_id)
    registrations = _query_active_registered_registrations(session, institution_id=institution_id, course_offering_ids=[class_session.course_offering_id])
    records = _query_active_attendance_records(
        session,
        institution_id=institution_id,
        class_session_ids=[class_session.id],
        course_registration_ids=[item.id for item in registrations],
    )
    counts = _count_statuses(records)
    eligible_count = len(registrations)
    marked_count = sum(counts.values())
    return ClassSessionAttendanceSummary(
        class_session_id=class_session.id,
        course_offering_id=class_session.course_offering_id,
        eligible_registration_count=eligible_count,
        marked_count=marked_count,
        present_count=counts["present"],
        late_count=counts["late"],
        absent_count=counts["absent"],
        excused_count=counts["excused"],
        unmarked_count=max(eligible_count - marked_count, 0),
        attendance_rate=_percentage(counts["present"] + counts["late"], eligible_count),
    )


def get_course_offering_attendance_summary(
    session: Session,
    *,
    institution_id: UUID,
    course_offering_id: UUID,
    minimum_percentage: float = DEFAULT_MINIMUM_PERCENTAGE,
    include_students: bool = False,
) -> CourseOfferingAttendanceSummary:
    _validate_minimum_percentage(minimum_percentage)
    offering = _resolve_course_offering(session, course_offering_id=course_offering_id, institution_id=institution_id)
    all_sessions = _query_all_class_sessions(session, institution_id=institution_id, course_offering_id=offering.id)
    eligible_sessions = [item for item in all_sessions if _is_eligible_session(item)]
    registrations = _query_active_registered_registrations(session, institution_id=institution_id, course_offering_ids=[offering.id])
    records = _query_active_attendance_records(
        session,
        institution_id=institution_id,
        class_session_ids=[item.id for item in eligible_sessions],
        course_registration_ids=[item.id for item in registrations],
    )
    summaries = _build_summaries(registrations, eligible_sessions, records, minimum_percentage)
    meeting = sum(item.meets_requirement for item in summaries)
    average = round(sum(item.attendance_percentage for item in summaries) / len(summaries), 2) if summaries else 0.0
    return CourseOfferingAttendanceSummary(
        course_offering_id=offering.id,
        total_class_sessions=len(all_sessions),
        completed_class_sessions=len(eligible_sessions),
        active_registration_count=len(registrations),
        attendance_record_count=len(records),
        average_attendance_percentage=average,
        students_meeting_requirement=meeting,
        students_below_requirement=len(summaries) - meeting,
        minimum_required_percentage=minimum_percentage,
        student_summaries=summaries if include_students else None,
    )


def list_at_risk_course_registrations(
    session: Session,
    *,
    institution_id: UUID,
    minimum_percentage: float = DEFAULT_MINIMUM_PERCENTAGE,
    course_offering_id: UUID | None = None,
) -> AttendanceRiskListResponse:
    _validate_minimum_percentage(minimum_percentage)
    if course_offering_id is not None:
        _resolve_course_offering(session, course_offering_id=course_offering_id, institution_id=institution_id)
    registrations = _query_active_registered_registrations(
        session,
        institution_id=institution_id,
        course_offering_ids=[course_offering_id] if course_offering_id is not None else None,
        load_students=True,
    )
    offering_ids = list({item.course_offering_id for item in registrations})
    eligible_sessions = _query_eligible_completed_sessions(session, institution_id=institution_id, course_offering_ids=offering_ids)
    records = _query_active_attendance_records(
        session,
        institution_id=institution_id,
        class_session_ids=[item.id for item in eligible_sessions],
        course_registration_ids=[item.id for item in registrations],
    )
    summaries = _build_summaries(registrations, eligible_sessions, records, minimum_percentage)
    by_registration = {item.course_registration_id: item for item in summaries}
    items = [
        AttendanceRiskItem(
            course_registration_id=registration.id,
            student_id=registration.student_id,
            matriculation_number=registration.student.matriculation_number,
            student_name=_student_display_name(registration.student),
            course_offering_id=registration.course_offering_id,
            attendance_percentage=summary.attendance_percentage,
            minimum_required_percentage=minimum_percentage,
            shortfall_percentage=round(minimum_percentage - summary.attendance_percentage, 2),
        )
        for registration in registrations
        if (summary := by_registration[registration.id]).attendance_percentage < minimum_percentage
    ]
    items.sort(key=lambda item: (item.attendance_percentage, item.student_id.hex))
    return AttendanceRiskListResponse(minimum_required_percentage=minimum_percentage, total_at_risk=len(items), items=items)


def _resolve_course_registration(session: Session, *, course_registration_id: UUID, institution_id: UUID) -> CourseRegistration:
    item = session.scalar(select(CourseRegistration).where(
        CourseRegistration.id == course_registration_id,
        CourseRegistration.institution_id == institution_id,
        CourseRegistration.status == "active",
        CourseRegistration.registration_status == "registered",
    ))
    if item is None:
        raise AttendanceAnalyticsRegistrationNotFoundError()
    return item


def _resolve_class_session(session: Session, *, class_session_id: UUID, institution_id: UUID) -> ClassSession:
    item = session.scalar(select(ClassSession).where(ClassSession.id == class_session_id, ClassSession.institution_id == institution_id, ClassSession.status != "inactive"))
    if item is None:
        raise AttendanceAnalyticsClassSessionNotFoundError()
    return item


def _resolve_course_offering(session: Session, *, course_offering_id: UUID, institution_id: UUID) -> CourseOffering:
    item = session.scalar(select(CourseOffering).where(CourseOffering.id == course_offering_id, CourseOffering.institution_id == institution_id))
    if item is None:
        raise AttendanceAnalyticsCourseOfferingNotFoundError()
    return item


def _query_all_class_sessions(session: Session, *, institution_id: UUID, course_offering_id: UUID) -> list[ClassSession]:
    return list(session.scalars(select(ClassSession).where(ClassSession.institution_id == institution_id, ClassSession.course_offering_id == course_offering_id, ClassSession.status != "inactive")).all())


def _query_eligible_completed_sessions(session: Session, *, institution_id: UUID, course_offering_ids: list[UUID]) -> list[ClassSession]:
    if not course_offering_ids:
        return []
    return list(session.scalars(select(ClassSession).where(
        ClassSession.institution_id == institution_id,
        ClassSession.course_offering_id.in_(course_offering_ids),
        ClassSession.status == "completed",
        ClassSession.session_date <= date.today(),
    )).all())


def _query_active_registered_registrations(session: Session, *, institution_id: UUID, course_offering_ids: list[UUID] | None, load_students: bool = False) -> list[CourseRegistration]:
    statement = select(CourseRegistration).where(
        CourseRegistration.institution_id == institution_id,
        CourseRegistration.status == "active",
        CourseRegistration.registration_status == "registered",
    )
    if course_offering_ids is not None:
        if not course_offering_ids:
            return []
        statement = statement.where(CourseRegistration.course_offering_id.in_(course_offering_ids))
    if load_students:
        statement = statement.options(joinedload(CourseRegistration.student).joinedload(Student.user))
    return list(session.scalars(statement).all())


def _query_active_attendance_records(session: Session, *, institution_id: UUID, class_session_ids: list[UUID], course_registration_ids: list[UUID]) -> list[AttendanceRecord]:
    if not class_session_ids or not course_registration_ids:
        return []
    return list(session.scalars(select(AttendanceRecord).where(
        AttendanceRecord.institution_id == institution_id,
        AttendanceRecord.status == "active",
        AttendanceRecord.class_session_id.in_(class_session_ids),
        AttendanceRecord.course_registration_id.in_(course_registration_ids),
    )).all())


def _build_summaries(registrations: list[CourseRegistration], eligible_sessions: list[ClassSession], records: list[AttendanceRecord], minimum_percentage: float) -> list[CourseRegistrationAttendanceSummary]:
    sessions_by_offering: dict[UUID, list[ClassSession]] = defaultdict(list)
    records_by_registration: dict[UUID, list[AttendanceRecord]] = defaultdict(list)
    for item in eligible_sessions: sessions_by_offering[item.course_offering_id].append(item)
    for item in records: records_by_registration[item.course_registration_id].append(item)
    return [_build_registration_summary(item, sessions_by_offering[item.course_offering_id], records_by_registration[item.id], minimum_percentage) for item in registrations]


def _build_registration_summary(registration: CourseRegistration, eligible_sessions: list[ClassSession], records: list[AttendanceRecord], minimum_percentage: float) -> CourseRegistrationAttendanceSummary:
    eligible_ids = {item.id for item in eligible_sessions}
    active_records = [item for item in records if item.status == "active" and item.class_session_id in eligible_ids]
    counts = _count_statuses(active_records)
    recorded = sum(counts.values())
    effective = recorded - counts["excused"]
    percentage = _percentage(counts["present"] + counts["late"], effective)
    return CourseRegistrationAttendanceSummary(
        course_registration_id=registration.id,
        student_id=registration.student_id,
        course_offering_id=registration.course_offering_id,
        total_sessions=len(eligible_sessions),
        recorded_sessions=recorded,
        present_count=counts["present"], late_count=counts["late"], absent_count=counts["absent"], excused_count=counts["excused"],
        unmarked_count=max(len(eligible_sessions) - recorded, 0),
        effective_session_count=effective,
        attendance_percentage=percentage,
        minimum_required_percentage=minimum_percentage,
        meets_requirement=percentage >= minimum_percentage,
    )


def _count_statuses(records: list[AttendanceRecord]) -> dict[str, int]:
    counts = dict.fromkeys(ATTENDANCE_STATUSES, 0)
    for item in records:
        if item.attendance_status in counts:
            counts[item.attendance_status] += 1
    return counts


def _percentage(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _validate_minimum_percentage(value: float) -> None:
    if not 0 <= value <= 100:
        raise InvalidMinimumPercentageError()


def _is_eligible_session(item: ClassSession) -> bool:
    return item.status == "completed" and item.session_date <= date.today()


def _student_display_name(student: Student) -> str:
    user = student.user
    if user is None:
        return student.matriculation_number
    name = " ".join(part.strip() for part in (user.first_name, user.last_name) if part and part.strip())
    return name or student.matriculation_number
