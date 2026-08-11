from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.assessment_component import AssessmentComponent
from app.models.assessment_score import AssessmentScore
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.examination import Examination
from app.models.examination_score import ExaminationScore
from app.services import result_computation_service as service
from app.services.grading_policy import resolve_default_grade


def registration(*, state: str = "registered", status: str = "active") -> CourseRegistration:
    now = datetime.now(UTC)
    return CourseRegistration(id=uuid4(), institution_id=uuid4(), student_id=uuid4(), course_offering_id=uuid4(), registration_status=state, registered_at=now, status=status, created_at=now, updated_at=now)


def component(enrolled: CourseRegistration, weight: str, maximum: str = "20", *, status: str = "published", kind: str = "quiz") -> AssessmentComponent:
    now = datetime.now(UTC)
    return AssessmentComponent(id=uuid4(), institution_id=enrolled.institution_id, course_offering_id=enrolled.course_offering_id, lecturer_assignment_id=uuid4(), title=kind, assessment_type=kind, maximum_score=Decimal(maximum), weight_percentage=Decimal(weight), status=status, created_at=now, updated_at=now)


def examination(enrolled: CourseRegistration, weight: str, maximum: str = "100", *, status: str = "completed") -> Examination:
    now = datetime.now(UTC)
    return Examination(id=uuid4(), institution_id=enrolled.institution_id, course_offering_id=enrolled.course_offering_id, lecturer_assignment_id=uuid4(), title="Exam", examination_type="written", maximum_score=Decimal(maximum), weight_percentage=Decimal(weight), exam_date=date.today(), start_time=time(9), end_time=time(11), delivery_mode="physical", status=status, created_at=now, updated_at=now)


def assessment_score(enrolled: CourseRegistration, item: AssessmentComponent, value: str, *, status: str = "active") -> AssessmentScore:
    now = datetime.now(UTC)
    return AssessmentScore(id=uuid4(), institution_id=enrolled.institution_id, assessment_component_id=item.id, course_registration_id=enrolled.id, score=Decimal(value), graded_by_user_id=uuid4(), graded_at=now, status=status, created_at=now, updated_at=now)


def exam_score(enrolled: CourseRegistration, item: Examination, value: str, *, status: str = "active") -> ExaminationScore:
    now = datetime.now(UTC)
    return ExaminationScore(id=uuid4(), institution_id=enrolled.institution_id, examination_id=item.id, course_registration_id=enrolled.id, score=Decimal(value), graded_by_user_id=uuid4(), graded_at=now, status=status, created_at=now, updated_at=now)


def test_weighted_decimal_computation_multiple_sources_and_serialization() -> None:
    enrolled = registration(); first = component(enrolled, "20", "30"); second = component(enrolled, "20", "15"); exam = examination(enrolled, "60")
    result = service._build_result(enrolled, [first, second], [exam], [assessment_score(enrolled, first, "20"), assessment_score(enrolled, second, "10")], [exam_score(enrolled, exam, "75")])
    assert result.continuous_assessment_score == Decimal("26.67")
    assert result.examination_score == Decimal("45.00") and result.final_score == Decimal("71.67")
    assert result.is_complete and (result.grade_letter, result.grade_point, result.passed) == ("A", Decimal("5.00"), True)
    assert result.model_dump(mode="json")["final_score"] == "71.67"


@pytest.mark.parametrize(("weight", "complete"), [("99.99", False), ("100.00", True), ("100.01", False)])
def test_configuration_must_equal_exactly_one_hundred(weight: str, complete: bool) -> None:
    enrolled = registration(); item = component(enrolled, weight)
    result = service._build_result(enrolled, [item], [], [assessment_score(enrolled, item, "20")], [])
    assert result.is_complete is complete
    assert (result.grade_letter is not None) is complete


def test_missing_and_inactive_scores_are_not_zero_or_failed() -> None:
    enrolled = registration(); item = component(enrolled, "100"); inactive = assessment_score(enrolled, item, "20", status="inactive")
    for scores in ([], [inactive]):
        result = service._build_result(enrolled, [item], [], scores, [])
        assert result.final_score == Decimal("0.00") and not result.is_complete
        assert result.grade_letter is result.grade_point is result.passed is None
        assert result.missing_components[0].reason == "score_missing" and not result.contributions


@pytest.mark.parametrize(("score", "letter", "point", "passed"), [("70", "A", "5", True), ("60", "B", "4", True), ("50", "C", "3", True), ("45", "D", "2", True), ("40", "E", "1", True), ("39.99", "F", "0", False)])
def test_exact_grade_boundaries(score: str, letter: str, point: str, passed: bool) -> None:
    grade = resolve_default_grade(Decimal(score))
    assert (grade.letter, grade.point, grade.passed) == (letter, Decimal(point), passed)


@pytest.mark.parametrize(("state", "status"), [("dropped", "active"), ("registered", "inactive")])
def test_unavailable_registration_rejected(state: str, status: str) -> None:
    with pytest.raises(service.ResultCourseRegistrationUnavailableError):
        service._ensure_registration_available(registration(state=state, status=status))


def test_attendance_and_other_types_use_normal_formula() -> None:
    enrolled = registration(); items = [component(enrolled, "50", kind="attendance"), component(enrolled, "50", kind="other")]
    scores = [assessment_score(enrolled, item, "10") for item in items]
    result = service._build_result(enrolled, items, [], scores, [])
    assert result.final_score == Decimal("50.00") and len(result.contributions) == 2


def test_offering_aggregate_builder_counts_only_complete_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    enrolled = registration(); offering = CourseOffering(id=enrolled.course_offering_id, institution_id=enrolled.institution_id, course_id=uuid4(), academic_session_id=uuid4(), semester_id=uuid4(), registration_open=False, status="active")
    item = component(enrolled, "100"); score = assessment_score(enrolled, item, "0")
    values = iter([offering, [enrolled], [item], [], [score], []])
    class Result:
        def __init__(self, value: object): self.value = value
        def all(self) -> object: return self.value
    class Session:
        def scalar(self, _: object) -> object: return next(values)
        def scalars(self, _: object) -> Result: return Result(next(values))
    result = service.compute_course_offering_results(Session(), institution_id=enrolled.institution_id, course_offering_id=offering.id)  # type: ignore[arg-type]
    assert (result.total_registrations, result.complete_results, result.incomplete_results, result.passed_count, result.failed_count) == (1, 1, 0, 0, 1)
