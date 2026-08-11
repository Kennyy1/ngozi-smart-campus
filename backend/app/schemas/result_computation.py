from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WeightedScoreContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["assessment", "examination"]
    source_id: UUID
    title: str
    maximum_score: Decimal
    weight_percentage: Decimal
    student_score: Decimal
    weighted_score: Decimal


class MissingResultComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["assessment", "examination"]
    source_id: UUID
    title: str
    reason: Literal["score_missing"]


class ComputedCourseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_registration_id: UUID
    student_id: UUID
    course_offering_id: UUID
    assessment_weight_total: Decimal
    examination_weight_total: Decimal
    configured_weight_total: Decimal
    continuous_assessment_score: Decimal
    examination_score: Decimal
    final_score: Decimal
    is_complete: bool
    grade_letter: str | None
    grade_point: Decimal | None
    passed: bool | None
    contributions: list[WeightedScoreContribution]
    missing_components: list[MissingResultComponent]


class CourseOfferingComputedResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_offering_id: UUID
    total_registrations: int
    complete_results: int
    incomplete_results: int
    passed_count: int
    failed_count: int
    results: list[ComputedCourseResult]
