from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment_component import AssessmentComponent
from app.models.assessment_score import AssessmentScore
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.examination import Examination
from app.models.examination_score import ExaminationScore
from app.schemas.result_computation import (
    ComputedCourseResult,
    CourseOfferingComputedResults,
    MissingResultComponent,
    WeightedScoreContribution,
)
from app.services.grading_policy import resolve_default_grade


TWO_PLACES = Decimal("0.01")
REQUIRED_WEIGHT = Decimal("100.00")


class ResultCourseRegistrationNotFoundError(Exception): pass
class ResultCourseRegistrationUnavailableError(Exception): pass
class ResultCourseOfferingNotFoundError(Exception): pass


def compute_course_registration_result(
    session: Session, *, institution_id: UUID, course_registration_id: UUID
) -> ComputedCourseResult:
    registration = _resolve_course_registration(session, institution_id=institution_id, course_registration_id=course_registration_id)
    _ensure_registration_available(registration)
    _resolve_course_offering(session, institution_id=institution_id, course_offering_id=registration.course_offering_id)
    components = _query_result_bearing_assessment_components(session, institution_id=institution_id, course_offering_id=registration.course_offering_id)
    examinations = _query_completed_examinations(session, institution_id=institution_id, course_offering_id=registration.course_offering_id)
    assessment_scores = _query_active_assessment_scores(session, institution_id=institution_id, course_registration_ids=[registration.id])
    examination_scores = _query_active_examination_scores(session, institution_id=institution_id, course_registration_ids=[registration.id])
    return _build_result(registration, components, examinations, assessment_scores, examination_scores)


def compute_course_offering_results(
    session: Session, *, institution_id: UUID, course_offering_id: UUID
) -> CourseOfferingComputedResults:
    offering = _resolve_course_offering(session, institution_id=institution_id, course_offering_id=course_offering_id)
    registrations = _query_active_registered_registrations(session, institution_id=institution_id, course_offering_id=offering.id)
    components = _query_result_bearing_assessment_components(session, institution_id=institution_id, course_offering_id=offering.id)
    examinations = _query_completed_examinations(session, institution_id=institution_id, course_offering_id=offering.id)
    registration_ids = [item.id for item in registrations]
    assessment_scores = _query_active_assessment_scores(session, institution_id=institution_id, course_registration_ids=registration_ids)
    examination_scores = _query_active_examination_scores(session, institution_id=institution_id, course_registration_ids=registration_ids)
    results = [_build_result(item, components, examinations, assessment_scores, examination_scores) for item in registrations]
    complete = sum(item.is_complete for item in results)
    return CourseOfferingComputedResults(
        course_offering_id=offering.id, total_registrations=len(results), complete_results=complete,
        incomplete_results=len(results) - complete,
        passed_count=sum(item.passed is True for item in results),
        failed_count=sum(item.passed is False for item in results), results=results,
    )


def _resolve_course_registration(session: Session, *, institution_id: UUID, course_registration_id: UUID) -> CourseRegistration:
    item = session.scalar(select(CourseRegistration).where(CourseRegistration.id == course_registration_id, CourseRegistration.institution_id == institution_id))
    if item is None: raise ResultCourseRegistrationNotFoundError()
    return item


def _ensure_registration_available(registration: CourseRegistration) -> None:
    if registration.status != "active" or registration.registration_status != "registered":
        raise ResultCourseRegistrationUnavailableError()


def _resolve_course_offering(session: Session, *, institution_id: UUID, course_offering_id: UUID) -> CourseOffering:
    item = session.scalar(select(CourseOffering).where(CourseOffering.id == course_offering_id, CourseOffering.institution_id == institution_id))
    if item is None: raise ResultCourseOfferingNotFoundError()
    return item


def _query_result_bearing_assessment_components(session: Session, *, institution_id: UUID, course_offering_id: UUID) -> list[AssessmentComponent]:
    return list(session.scalars(select(AssessmentComponent).where(AssessmentComponent.institution_id == institution_id, AssessmentComponent.course_offering_id == course_offering_id, AssessmentComponent.status.in_(("published", "closed")))).all())


def _query_completed_examinations(session: Session, *, institution_id: UUID, course_offering_id: UUID) -> list[Examination]:
    return list(session.scalars(select(Examination).where(Examination.institution_id == institution_id, Examination.course_offering_id == course_offering_id, Examination.status == "completed")).all())


def _query_active_registered_registrations(session: Session, *, institution_id: UUID, course_offering_id: UUID) -> list[CourseRegistration]:
    return list(session.scalars(select(CourseRegistration).where(CourseRegistration.institution_id == institution_id, CourseRegistration.course_offering_id == course_offering_id, CourseRegistration.status == "active", CourseRegistration.registration_status == "registered")).all())


def _query_active_assessment_scores(session: Session, *, institution_id: UUID, course_registration_ids: list[UUID]) -> list[AssessmentScore]:
    if not course_registration_ids: return []
    return list(session.scalars(select(AssessmentScore).where(AssessmentScore.institution_id == institution_id, AssessmentScore.course_registration_id.in_(course_registration_ids), AssessmentScore.status == "active")).all())


def _query_active_examination_scores(session: Session, *, institution_id: UUID, course_registration_ids: list[UUID]) -> list[ExaminationScore]:
    if not course_registration_ids: return []
    return list(session.scalars(select(ExaminationScore).where(ExaminationScore.institution_id == institution_id, ExaminationScore.course_registration_id.in_(course_registration_ids), ExaminationScore.status == "active")).all())


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _build_result(registration: CourseRegistration, components: Sequence[AssessmentComponent], examinations: Sequence[Examination], assessment_scores: Sequence[AssessmentScore], examination_scores: Sequence[ExaminationScore]) -> ComputedCourseResult:
    assessment_by_key = {(item.course_registration_id, item.assessment_component_id): item for item in assessment_scores if item.status == "active"}
    examination_by_key = {(item.course_registration_id, item.examination_id): item for item in examination_scores if item.status == "active"}
    contributions: list[WeightedScoreContribution] = []
    missing: list[MissingResultComponent] = []
    assessment_total = sum((Decimal(item.weight_percentage) for item in components), Decimal("0"))
    examination_total = sum((Decimal(item.weight_percentage) for item in examinations), Decimal("0"))
    ca_raw = Decimal("0"); exam_raw = Decimal("0")
    for source_type, sources, scores in (("assessment", components, assessment_by_key), ("examination", examinations, examination_by_key)):
        for source in sources:
            score = scores.get((registration.id, source.id))
            if score is None:
                missing.append(MissingResultComponent(source_type=source_type, source_id=source.id, title=source.title, reason="score_missing"))
                continue
            raw = Decimal(score.score) / Decimal(source.maximum_score) * Decimal(source.weight_percentage)
            if source_type == "assessment": ca_raw += raw
            else: exam_raw += raw
            contributions.append(WeightedScoreContribution(source_type=source_type, source_id=source.id, title=source.title, maximum_score=_rounded(Decimal(source.maximum_score)), weight_percentage=_rounded(Decimal(source.weight_percentage)), student_score=_rounded(Decimal(score.score)), weighted_score=_rounded(raw)))
    configured = assessment_total + examination_total
    is_complete = configured == REQUIRED_WEIGHT and not missing
    final_raw = ca_raw + exam_raw
    grade = resolve_default_grade(final_raw) if is_complete else None
    return ComputedCourseResult(
        course_registration_id=registration.id, student_id=registration.student_id, course_offering_id=registration.course_offering_id,
        assessment_weight_total=_rounded(assessment_total), examination_weight_total=_rounded(examination_total), configured_weight_total=_rounded(configured),
        continuous_assessment_score=_rounded(ca_raw), examination_score=_rounded(exam_raw), final_score=_rounded(final_raw), is_complete=is_complete,
        grade_letter=grade.letter if grade else None, grade_point=grade.point if grade else None, passed=grade.passed if grade else None,
        contributions=contributions, missing_components=missing,
    )
