from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assessment_component import AssessmentComponent
from app.models.assessment_score import AssessmentScore
from app.models.course_registration import CourseRegistration
from app.schemas.assessment_score import (
    AssessmentScoreBulkCreate,
    AssessmentScoreCreate,
    AssessmentScoreStatus,
    AssessmentScoreUpdate,
)


class AssessmentScoreNotFoundError(Exception): pass
class ScoreAssessmentComponentNotFoundError(Exception): pass
class ScoreCourseRegistrationNotFoundError(Exception): pass
class AssessmentComponentUnavailableForGradingError(Exception): pass
class ScoreCourseRegistrationUnavailableError(Exception): pass
class AssessmentScoreOfferingMismatchError(Exception): pass
class InvalidAssessmentScoreError(Exception): pass
class DuplicateAssessmentScoreError(Exception): pass
class AssessmentGraderUnauthorizedError(Exception): pass


def create_assessment_score(
    session: Session,
    *,
    institution_id: UUID,
    graded_by_user_id: UUID,
    assessment_score_data: AssessmentScoreCreate,
) -> AssessmentScore:
    component = _resolve_assessment_component(
        session, assessment_component_id=assessment_score_data.assessment_component_id, institution_id=institution_id
    )
    _validate_component_grading_availability(component)
    registration = _resolve_course_registration(
        session, course_registration_id=assessment_score_data.course_registration_id, institution_id=institution_id
    )
    _validate_registration_eligibility(registration)
    _validate_offering_match(component, registration)
    _validate_grader_authorization(graded_by_user_id)
    _validate_score_range(assessment_score_data.score, component.maximum_score)
    _ensure_score_available(session, assessment_component_id=component.id, course_registration_id=registration.id)
    score = AssessmentScore(
        institution_id=institution_id,
        assessment_component_id=component.id,
        course_registration_id=registration.id,
        score=assessment_score_data.score,
        graded_by_user_id=graded_by_user_id,
        graded_at=datetime.now(UTC),
        remarks=assessment_score_data.remarks,
        status=AssessmentScoreStatus.ACTIVE.value,
    )
    session.add(score)
    _commit(session)
    session.refresh(score)
    return score


def create_assessment_scores_bulk(
    session: Session,
    *,
    institution_id: UUID,
    graded_by_user_id: UUID,
    assessment_score_data: AssessmentScoreBulkCreate,
) -> list[AssessmentScore]:
    component = _resolve_assessment_component(
        session, assessment_component_id=assessment_score_data.assessment_component_id, institution_id=institution_id
    )
    _validate_component_grading_availability(component)
    _validate_grader_authorization(graded_by_user_id)
    registration_ids = [item.course_registration_id for item in assessment_score_data.scores]
    if len(registration_ids) != len(set(registration_ids)):
        raise InvalidAssessmentScoreError()

    resolved: list[tuple[CourseRegistration, object]] = []
    for item in assessment_score_data.scores:
        registration = _resolve_course_registration(
            session, course_registration_id=item.course_registration_id, institution_id=institution_id
        )
        _validate_registration_eligibility(registration)
        _validate_offering_match(component, registration)
        _validate_score_range(item.score, component.maximum_score)
        _ensure_score_available(session, assessment_component_id=component.id, course_registration_id=registration.id)
        resolved.append((registration, item))

    graded_at = datetime.now(UTC)
    scores = [
        AssessmentScore(
            institution_id=institution_id,
            assessment_component_id=component.id,
            course_registration_id=registration.id,
            score=item.score,
            graded_by_user_id=graded_by_user_id,
            graded_at=graded_at,
            remarks=item.remarks,
            status=AssessmentScoreStatus.ACTIVE.value,
        )
        for registration, item in resolved
    ]
    session.add_all(scores)
    _commit(session)
    for score in scores:
        session.refresh(score)
    return scores


def list_assessment_scores(
    session: Session,
    *,
    institution_id: UUID,
    assessment_component_id: UUID | None = None,
    course_registration_id: UUID | None = None,
    graded_by_user_id: UUID | None = None,
    status: AssessmentScoreStatus | None = None,
) -> list[AssessmentScore]:
    statement = select(AssessmentScore).where(AssessmentScore.institution_id == institution_id)
    if status is None:
        statement = statement.where(AssessmentScore.status == AssessmentScoreStatus.ACTIVE.value)
    else:
        statement = statement.where(AssessmentScore.status == status.value)
    for column, value in (
        (AssessmentScore.assessment_component_id, assessment_component_id),
        (AssessmentScore.course_registration_id, course_registration_id),
        (AssessmentScore.graded_by_user_id, graded_by_user_id),
    ):
        if value is not None:
            statement = statement.where(column == value)
    return list(session.scalars(statement.order_by(AssessmentScore.created_at.desc(), AssessmentScore.id)).all())


def get_assessment_score(session: Session, *, assessment_score_id: UUID, institution_id: UUID) -> AssessmentScore:
    score = session.scalar(select(AssessmentScore).where(
        AssessmentScore.id == assessment_score_id,
        AssessmentScore.institution_id == institution_id,
        AssessmentScore.status == AssessmentScoreStatus.ACTIVE.value,
    ))
    if score is None:
        raise AssessmentScoreNotFoundError()
    return score


def update_assessment_score(
    session: Session,
    *,
    assessment_score_id: UUID,
    institution_id: UUID,
    assessment_score_data: AssessmentScoreUpdate,
) -> AssessmentScore:
    score = get_assessment_score(session, assessment_score_id=assessment_score_id, institution_id=institution_id)
    changes = assessment_score_data.model_dump(exclude_unset=True, mode="python")
    final_score = changes.get("score", score.score)
    component = _resolve_assessment_component(
        session, assessment_component_id=score.assessment_component_id, institution_id=institution_id
    )
    _validate_score_range(final_score, component.maximum_score)
    for field, value in changes.items():
        setattr(score, field, value)
    # graded_at identifies the original grading event; edits preserve it.
    _commit(session)
    session.refresh(score)
    return score


def delete_assessment_score(session: Session, *, assessment_score_id: UUID, institution_id: UUID) -> None:
    score = get_assessment_score(session, assessment_score_id=assessment_score_id, institution_id=institution_id)
    score.status = AssessmentScoreStatus.INACTIVE.value
    _commit(session)


def _resolve_assessment_component(
    session: Session, *, assessment_component_id: UUID, institution_id: UUID
) -> AssessmentComponent:
    component = session.scalar(select(AssessmentComponent).where(
        AssessmentComponent.id == assessment_component_id,
        AssessmentComponent.institution_id == institution_id,
    ))
    if component is None:
        raise ScoreAssessmentComponentNotFoundError()
    return component


def _resolve_course_registration(
    session: Session, *, course_registration_id: UUID, institution_id: UUID
) -> CourseRegistration:
    registration = session.scalar(select(CourseRegistration).where(
        CourseRegistration.id == course_registration_id,
        CourseRegistration.institution_id == institution_id,
    ))
    if registration is None:
        raise ScoreCourseRegistrationNotFoundError()
    return registration


def _validate_component_grading_availability(component: AssessmentComponent) -> None:
    if component.status != "published":
        raise AssessmentComponentUnavailableForGradingError()


def _validate_registration_eligibility(registration: CourseRegistration) -> None:
    if registration.status != "active" or registration.registration_status != "registered":
        raise ScoreCourseRegistrationUnavailableError()


def _validate_offering_match(component: AssessmentComponent, registration: CourseRegistration) -> None:
    if component.course_offering_id != registration.course_offering_id:
        raise AssessmentScoreOfferingMismatchError()


def _validate_score_range(score: Decimal, maximum_score: Decimal) -> None:
    if score < Decimal("0") or score > maximum_score:
        raise InvalidAssessmentScoreError()


def _validate_grader_authorization(graded_by_user_id: UUID) -> None:
    if graded_by_user_id is None:
        raise AssessmentGraderUnauthorizedError()


def _ensure_score_available(
    session: Session, *, assessment_component_id: UUID, course_registration_id: UUID
) -> None:
    existing = session.scalar(select(AssessmentScore.id).where(
        AssessmentScore.assessment_component_id == assessment_component_id,
        AssessmentScore.course_registration_id == course_registration_id,
        AssessmentScore.status == AssessmentScoreStatus.ACTIVE.value,
    ))
    if existing is not None:
        raise DuplicateAssessmentScoreError()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateAssessmentScoreError() from error
