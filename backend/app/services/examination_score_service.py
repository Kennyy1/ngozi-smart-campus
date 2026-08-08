from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course_registration import CourseRegistration
from app.models.examination import Examination
from app.models.examination_score import ExaminationScore
from app.schemas.examination_score import ExaminationScoreBulkCreate, ExaminationScoreCreate, ExaminationScoreStatus, ExaminationScoreUpdate


class ExaminationScoreNotFoundError(Exception): pass
class ScoreExaminationNotFoundError(Exception): pass
class ExaminationScoreCourseRegistrationNotFoundError(Exception): pass
class ExaminationUnavailableForGradingError(Exception): pass
class ExaminationScoreCourseRegistrationUnavailableError(Exception): pass
class ExaminationScoreOfferingMismatchError(Exception): pass
class InvalidExaminationScoreError(Exception): pass
class DuplicateExaminationScoreError(Exception): pass
class ExaminationGraderUnauthorizedError(Exception): pass


def create_examination_score(session: Session, *, institution_id: UUID, graded_by_user_id: UUID, examination_score_data: ExaminationScoreCreate) -> ExaminationScore:
    examination = _resolve_examination(session, examination_id=examination_score_data.examination_id, institution_id=institution_id)
    _validate_examination_grading_availability(examination)
    registration = _resolve_course_registration(session, course_registration_id=examination_score_data.course_registration_id, institution_id=institution_id)
    _validate_registration_eligibility(registration)
    _validate_offering_match(examination, registration)
    _validate_grader_authorization(graded_by_user_id)
    _validate_score_range(examination_score_data.score, examination.maximum_score)
    _ensure_score_available(session, examination_id=examination.id, course_registration_id=registration.id)
    score = ExaminationScore(institution_id=institution_id, examination_id=examination.id, course_registration_id=registration.id, score=examination_score_data.score, graded_by_user_id=graded_by_user_id, graded_at=datetime.now(UTC), remarks=examination_score_data.remarks, status=ExaminationScoreStatus.ACTIVE.value)
    session.add(score); _commit(session); session.refresh(score)
    return score


def create_examination_scores_bulk(session: Session, *, institution_id: UUID, graded_by_user_id: UUID, examination_score_data: ExaminationScoreBulkCreate) -> list[ExaminationScore]:
    examination = _resolve_examination(session, examination_id=examination_score_data.examination_id, institution_id=institution_id)
    _validate_examination_grading_availability(examination); _validate_grader_authorization(graded_by_user_id)
    registration_ids = [item.course_registration_id for item in examination_score_data.scores]
    if len(registration_ids) != len(set(registration_ids)): raise InvalidExaminationScoreError()
    resolved: list[tuple[CourseRegistration, object]] = []
    try:
        for item in examination_score_data.scores:
            registration = _resolve_course_registration(session, course_registration_id=item.course_registration_id, institution_id=institution_id)
            _validate_registration_eligibility(registration); _validate_offering_match(examination, registration)
            _validate_score_range(item.score, examination.maximum_score)
            _ensure_score_available(session, examination_id=examination.id, course_registration_id=registration.id)
            resolved.append((registration, item))
    except Exception:
        session.rollback()
        raise
    graded_at = datetime.now(UTC)
    scores = [ExaminationScore(institution_id=institution_id, examination_id=examination.id, course_registration_id=registration.id, score=item.score, graded_by_user_id=graded_by_user_id, graded_at=graded_at, remarks=item.remarks, status=ExaminationScoreStatus.ACTIVE.value) for registration, item in resolved]
    session.add_all(scores); _commit(session)
    for score in scores: session.refresh(score)
    return scores


def list_examination_scores(session: Session, *, institution_id: UUID, examination_id: UUID | None = None, course_registration_id: UUID | None = None, graded_by_user_id: UUID | None = None, status: ExaminationScoreStatus | None = None) -> list[ExaminationScore]:
    statement = select(ExaminationScore).where(ExaminationScore.institution_id == institution_id)
    statement = statement.where(ExaminationScore.status == (status.value if status else ExaminationScoreStatus.ACTIVE.value))
    for column, value in ((ExaminationScore.examination_id, examination_id), (ExaminationScore.course_registration_id, course_registration_id), (ExaminationScore.graded_by_user_id, graded_by_user_id)):
        if value is not None: statement = statement.where(column == value)
    return list(session.scalars(statement.order_by(ExaminationScore.created_at.desc(), ExaminationScore.id)).all())


def get_examination_score(session: Session, *, examination_score_id: UUID, institution_id: UUID) -> ExaminationScore:
    score = session.scalar(select(ExaminationScore).where(ExaminationScore.id == examination_score_id, ExaminationScore.institution_id == institution_id, ExaminationScore.status == ExaminationScoreStatus.ACTIVE.value))
    if score is None: raise ExaminationScoreNotFoundError()
    return score


def update_examination_score(session: Session, *, examination_score_id: UUID, institution_id: UUID, examination_score_data: ExaminationScoreUpdate) -> ExaminationScore:
    score = get_examination_score(session, examination_score_id=examination_score_id, institution_id=institution_id)
    changes = examination_score_data.model_dump(exclude_unset=True, mode="python")
    examination = _resolve_examination(session, examination_id=score.examination_id, institution_id=institution_id)
    _validate_score_range(changes.get("score", score.score), examination.maximum_score)
    for field, value in changes.items(): setattr(score, field, value)
    # Preserve graded_at as the original grading event, matching AssessmentScore.
    _commit(session); session.refresh(score)
    return score


def delete_examination_score(session: Session, *, examination_score_id: UUID, institution_id: UUID) -> None:
    score = get_examination_score(session, examination_score_id=examination_score_id, institution_id=institution_id)
    score.status = ExaminationScoreStatus.INACTIVE.value; _commit(session)


def _resolve_examination(session: Session, *, examination_id: UUID, institution_id: UUID) -> Examination:
    examination = session.scalar(select(Examination).where(Examination.id == examination_id, Examination.institution_id == institution_id))
    if examination is None: raise ScoreExaminationNotFoundError()
    return examination


def _resolve_course_registration(session: Session, *, course_registration_id: UUID, institution_id: UUID) -> CourseRegistration:
    registration = session.scalar(select(CourseRegistration).where(CourseRegistration.id == course_registration_id, CourseRegistration.institution_id == institution_id))
    if registration is None: raise ExaminationScoreCourseRegistrationNotFoundError()
    return registration


def _validate_examination_grading_availability(examination: Examination) -> None:
    if examination.status != "completed": raise ExaminationUnavailableForGradingError()


def _validate_registration_eligibility(registration: CourseRegistration) -> None:
    if registration.status != "active" or registration.registration_status != "registered": raise ExaminationScoreCourseRegistrationUnavailableError()


def _validate_offering_match(examination: Examination, registration: CourseRegistration) -> None:
    if examination.course_offering_id != registration.course_offering_id: raise ExaminationScoreOfferingMismatchError()


def _validate_score_range(score: Decimal, maximum_score: Decimal) -> None:
    if score < Decimal("0") or score > maximum_score: raise InvalidExaminationScoreError()


def _validate_grader_authorization(graded_by_user_id: UUID) -> None:
    if graded_by_user_id is None: raise ExaminationGraderUnauthorizedError()


def _ensure_score_available(session: Session, *, examination_id: UUID, course_registration_id: UUID) -> None:
    existing = session.scalar(select(ExaminationScore.id).where(ExaminationScore.examination_id == examination_id, ExaminationScore.course_registration_id == course_registration_id, ExaminationScore.status == ExaminationScoreStatus.ACTIVE.value))
    if existing is not None: raise DuplicateExaminationScoreError()


def _commit(session: Session) -> None:
    try: session.commit()
    except IntegrityError as error:
        session.rollback(); raise DuplicateExaminationScoreError() from error
