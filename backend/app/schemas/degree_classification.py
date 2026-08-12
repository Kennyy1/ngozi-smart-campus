from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.services.academic_progression_policy import AcademicStanding
from app.services.degree_classification_policy import DegreeClassification, GraduationOutcome
from app.services.graduation_policy import GraduationEligibilityReason


class DegreeClassificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cgpa: Decimal
    classification: DegreeClassification
    classification_label: str
    classification_policy: str
    minimum_cgpa: Decimal | None
    maximum_cgpa: Decimal


class GraduationOutcomeEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    matriculation_number: str
    student_name: str
    programme_id: UUID
    programme_name: str
    programme_code: str
    current_level: str | None
    cgpa: Decimal
    academic_standing: AcademicStanding
    eligible_for_graduation: bool
    graduation_eligibility_reasons: list[GraduationEligibilityReason]
    graduation_outcome: GraduationOutcome
    degree_classification: DegreeClassification | None
    degree_classification_label: str | None
    classification_policy: str
    outstanding_failed_course_count: int
    cumulative_attempted_units: int
    cumulative_earned_units: int
    evaluated_at: datetime
