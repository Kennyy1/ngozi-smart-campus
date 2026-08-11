from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course_registration import CourseRegistration
from app.models.result import Result
from app.schemas.result import ResultCreate, ResultRejectRequest, ResultStatus, ResultUpdate
from app.schemas.result_computation import ComputedCourseResult
from app.services.result_computation_service import compute_course_registration_result


class ResultNotFoundError(Exception): pass
class ResultCourseRegistrationNotFoundError(Exception): pass
class ResultCourseRegistrationUnavailableError(Exception): pass
class DuplicateResultError(Exception): pass
class IncompleteResultComputationError(Exception): pass
class InvalidResultTransitionError(Exception): pass
class ResultImmutableError(Exception): pass


def create_result(session: Session, *, institution_id: UUID, computed_by_user_id: UUID, result_data: ResultCreate) -> Result:
    registration = _resolve_course_registration(session, institution_id=institution_id, course_registration_id=result_data.course_registration_id)
    _ensure_registration_available(registration)
    if _active_result_exists(session, institution_id=institution_id, course_registration_id=registration.id):
        raise DuplicateResultError()
    computed = compute_course_registration_result(session, institution_id=institution_id, course_registration_id=registration.id)
    _require_complete(computed)
    now = datetime.now(UTC)
    result = Result(
        institution_id=institution_id, course_registration_id=registration.id,
        course_offering_id=registration.course_offering_id, student_id=registration.student_id,
        status=ResultStatus.DRAFT.value, computed_at=now, computed_by_user_id=computed_by_user_id,
        remarks=result_data.remarks,
    )
    _copy_snapshot(result, computed)
    session.add(result)
    _commit(session, DuplicateResultError)
    session.refresh(result)
    return result


def list_results(session: Session, *, institution_id: UUID, course_registration_id: UUID | None = None, course_offering_id: UUID | None = None, student_id: UUID | None = None, status: ResultStatus | None = None, passed: bool | None = None, grade_letter: str | None = None) -> list[Result]:
    statement = select(Result).where(Result.institution_id == institution_id, Result.status != ResultStatus.INACTIVE.value)
    for column, value in ((Result.course_registration_id, course_registration_id), (Result.course_offering_id, course_offering_id), (Result.student_id, student_id), (Result.status, status.value if status else None), (Result.passed, passed), (Result.grade_letter, grade_letter)):
        if value is not None: statement = statement.where(column == value)
    return list(session.scalars(statement).all())


def get_result(session: Session, *, institution_id: UUID, result_id: UUID) -> Result:
    return _resolve_result(session, institution_id=institution_id, result_id=result_id)


def update_result(session: Session, *, institution_id: UUID, result_id: UUID, result_data: ResultUpdate) -> Result:
    result = _resolve_result(session, institution_id=institution_id, result_id=result_id)
    if result.status != ResultStatus.DRAFT.value: raise ResultImmutableError()
    if "remarks" in result_data.model_fields_set: result.remarks = result_data.remarks
    session.commit(); session.refresh(result)
    return result


def refresh_result(session: Session, *, institution_id: UUID, result_id: UUID, computed_by_user_id: UUID) -> Result:
    result = _resolve_result(session, institution_id=institution_id, result_id=result_id)
    if result.status != ResultStatus.DRAFT.value: raise ResultImmutableError()
    computed = compute_course_registration_result(session, institution_id=institution_id, course_registration_id=result.course_registration_id)
    _require_complete(computed); _copy_snapshot(result, computed)
    result.computed_at = datetime.now(UTC); result.computed_by_user_id = computed_by_user_id
    session.commit(); session.refresh(result)
    return result


def submit_result(session: Session, *, institution_id: UUID, result_id: UUID, user_id: UUID) -> Result:
    return _transition(session, institution_id=institution_id, result_id=result_id, allowed={"draft"}, target="submitted", actor_field="submitted_by_user_id", time_field="submitted_at", user_id=user_id)


def approve_result(session: Session, *, institution_id: UUID, result_id: UUID, user_id: UUID) -> Result:
    return _transition(session, institution_id=institution_id, result_id=result_id, allowed={"submitted"}, target="approved", actor_field="approved_by_user_id", time_field="approved_at", user_id=user_id)


def reject_result(session: Session, *, institution_id: UUID, result_id: UUID, user_id: UUID, request: ResultRejectRequest) -> Result:
    result = _transition(session, institution_id=institution_id, result_id=result_id, allowed={"submitted"}, target="rejected", user_id=user_id, commit=False)
    result.remarks = request.reason
    session.commit(); session.refresh(result)
    return result


def return_result_to_draft(session: Session, *, institution_id: UUID, result_id: UUID, user_id: UUID) -> Result:
    return _transition(session, institution_id=institution_id, result_id=result_id, allowed={"rejected"}, target="draft", user_id=user_id)


def publish_result(session: Session, *, institution_id: UUID, result_id: UUID, user_id: UUID) -> Result:
    return _transition(session, institution_id=institution_id, result_id=result_id, allowed={"approved", "withheld"}, target="published", actor_field="published_by_user_id", time_field="published_at", user_id=user_id)


def withhold_result(session: Session, *, institution_id: UUID, result_id: UUID, user_id: UUID) -> Result:
    return _transition(session, institution_id=institution_id, result_id=result_id, allowed={"approved", "published"}, target="withheld", user_id=user_id)


def _resolve_result(session: Session, *, institution_id: UUID, result_id: UUID) -> Result:
    item = session.scalar(select(Result).where(Result.id == result_id, Result.institution_id == institution_id, Result.status != ResultStatus.INACTIVE.value))
    if item is None: raise ResultNotFoundError()
    return item


def _resolve_course_registration(session: Session, *, institution_id: UUID, course_registration_id: UUID) -> CourseRegistration:
    item = session.scalar(select(CourseRegistration).where(CourseRegistration.id == course_registration_id, CourseRegistration.institution_id == institution_id))
    if item is None: raise ResultCourseRegistrationNotFoundError()
    return item


def _ensure_registration_available(registration: CourseRegistration) -> None:
    if registration.status != "active" or registration.registration_status != "registered": raise ResultCourseRegistrationUnavailableError()


def _active_result_exists(session: Session, *, institution_id: UUID, course_registration_id: UUID) -> bool:
    return session.scalar(select(Result.id).where(Result.institution_id == institution_id, Result.course_registration_id == course_registration_id, Result.status != ResultStatus.INACTIVE.value)) is not None


def _require_complete(computed: ComputedCourseResult) -> None:
    if not computed.is_complete: raise IncompleteResultComputationError()


def _copy_snapshot(result: Result, computed: ComputedCourseResult) -> None:
    if computed.grade_letter is None or computed.grade_point is None or computed.passed is None: raise IncompleteResultComputationError()
    result.continuous_assessment_score = computed.continuous_assessment_score
    result.examination_score = computed.examination_score
    result.final_score = computed.final_score
    result.grade_letter = computed.grade_letter
    result.grade_point = computed.grade_point
    result.passed = computed.passed


def _transition(session: Session, *, institution_id: UUID, result_id: UUID, allowed: set[str], target: str, user_id: UUID, actor_field: str | None = None, time_field: str | None = None, commit: bool = True) -> Result:
    result = _resolve_result(session, institution_id=institution_id, result_id=result_id)
    if result.status not in allowed: raise InvalidResultTransitionError()
    result.status = target
    now = datetime.now(UTC)
    if actor_field: setattr(result, actor_field, user_id)
    if time_field: setattr(result, time_field, now)
    if commit: session.commit(); session.refresh(result)
    return result


def _commit(session: Session, error_type: type[Exception]) -> None:
    try: session.commit()
    except IntegrityError as error:
        session.rollback()
        raise error_type() from error
