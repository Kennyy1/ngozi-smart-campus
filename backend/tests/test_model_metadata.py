from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.dialects import postgresql

import app.models  # noqa: F401
from app.db.base import Base


EXPECTED_TABLES = {
    "assessment_components",
    "assessment_scores",
    "attendance_records",
    "class_sessions",
    "academic_levels",
    "academic_sessions",
    "audit_logs",
    "courses",
    "course_offerings",
    "course_registrations",
    "course_materials",
    "mobile_app_releases",
    "departments",
    "faculties",
    "examinations",
    "examination_scores",
    "institutions",
    "institution_settings",
    "official_transcripts",
    "graduation_records",
    "academic_documents",
    "clearance_requirements",
    "student_clearances",
    "guardians",
    "guardian_students",
    "lecturers",
    "lecturer_assignments",
    "programmes",
    "results",
    "roles",
    "semesters",
    "students",
    "users",
    "user_roles",
}


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_target(table_name: str, column_name: str) -> str:
    column = Base.metadata.tables[table_name].columns[column_name]
    return next(iter(column.foreign_keys)).target_fullname


def test_all_models_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_guardian_defaults_and_active_relationship_index() -> None:
    guardians = Base.metadata.tables["guardians"]
    relationships = Base.metadata.tables["guardian_students"]

    assert str(guardians.c.is_active.server_default.arg).lower() == "true"
    for column_name in (
        "is_primary",
        "can_view_results",
        "can_view_attendance",
        "can_view_academic_performance",
        "can_view_transcript",
        "can_view_clearance",
    ):
        assert str(relationships.c[column_name].server_default.arg).lower() == "false"
    assert str(relationships.c.status.server_default.arg) == "pending"

    index = next(
        item
        for item in relationships.indexes
        if item.name == "uq_guardian_students_active_pair"
    )
    assert isinstance(index, Index)
    assert index.unique is True
    assert tuple(column.name for column in index.columns) == ("guardian_id", "student_id")
    predicate = index.dialect_options["postgresql"]["where"]
    compiled = str(predicate.compile(dialect=postgresql.dialect()))
    assert compiled == "status <> 'revoked'"


def test_expected_unique_constraints() -> None:
    assert ("document_reference",) in _unique_column_sets("academic_documents")
    assert ("verification_code",) in _unique_column_sets("academic_documents")
    assert ("graduation_reference",) in _unique_column_sets("graduation_records")
    assert ("institution_id", "transcript_reference") in _unique_column_sets("official_transcripts")
    assert (
        "course_id",
        "academic_session_id",
        "semester_id",
    ) in _unique_column_sets("course_offerings")
    assert ("institution_id", "code") in _unique_column_sets("courses")
    assert (
        "programme_id",
        "academic_level_id",
        "title",
    ) in _unique_column_sets("courses")
    assert ("programme_id", "name") in _unique_column_sets("academic_levels")
    assert ("programme_id", "code") in _unique_column_sets("academic_levels")
    assert (
        "programme_id",
        "sequence_number",
    ) in _unique_column_sets("academic_levels")
    assert ("code",) in _unique_column_sets("institutions")
    assert ("name",) in _unique_column_sets("roles")
    assert ("institution_id", "email") in _unique_column_sets("users")
    assert (
        "institution_id",
        "setting_key",
    ) in _unique_column_sets("institution_settings")
    assert (
        "user_id",
        "role_id",
        "institution_id",
    ) in _unique_column_sets("user_roles")
    assert ("institution_id", "code") in _unique_column_sets("faculties")
    assert ("institution_id", "name") in _unique_column_sets("faculties")
    assert ("institution_id", "code") in _unique_column_sets("departments")
    assert ("faculty_id", "name") in _unique_column_sets("departments")
    assert ("institution_id", "code") in _unique_column_sets("programmes")
    assert ("department_id", "name") in _unique_column_sets("programmes")
    assert (
        "institution_id",
        "name",
    ) in _unique_column_sets("academic_sessions")
    assert ("academic_session_id", "name") in _unique_column_sets("semesters")
    assert ("academic_session_id", "sequence_number") in _unique_column_sets("semesters")
    assert (
        "institution_id",
        "matriculation_number",
    ) in _unique_column_sets("students")
    assert ("user_id",) in _unique_column_sets("students")
    assert (
        "institution_id",
        "staff_number",
    ) in _unique_column_sets("lecturers")
    assert ("user_id",) in _unique_column_sets("lecturers")


def test_expected_foreign_keys() -> None:
    assert _foreign_key_target("academic_documents", "institution_id") == "institutions.id"
    assert _foreign_key_target("academic_documents", "student_id") == "students.id"
    assert _foreign_key_target("academic_documents", "programme_id") == "programmes.id"
    assert _foreign_key_target("academic_documents", "graduation_record_id") == "graduation_records.id"
    assert _foreign_key_target("academic_documents", "official_transcript_id") == "official_transcripts.id"
    assert _foreign_key_target("academic_documents", "generated_by_user_id") == "users.id"
    assert _foreign_key_target("academic_documents", "issued_by_user_id") == "users.id"
    assert _foreign_key_target("academic_documents", "revoked_by_user_id") == "users.id"
    assert _foreign_key_target("graduation_records", "institution_id") == "institutions.id"
    assert _foreign_key_target("graduation_records", "student_id") == "students.id"
    assert _foreign_key_target("graduation_records", "programme_id") == "programmes.id"
    assert _foreign_key_target("graduation_records", "prepared_by_user_id") == "users.id"
    assert _foreign_key_target("graduation_records", "confirmed_by_user_id") == "users.id"
    assert _foreign_key_target("graduation_records", "revoked_by_user_id") == "users.id"
    assert _foreign_key_target("official_transcripts", "institution_id") == "institutions.id"
    assert _foreign_key_target("official_transcripts", "student_id") == "students.id"
    assert _foreign_key_target("official_transcripts", "programme_id") == "programmes.id"
    assert _foreign_key_target("official_transcripts", "generated_by_user_id") == "users.id"
    assert _foreign_key_target("official_transcripts", "issued_by_user_id") == "users.id"
    assert _foreign_key_target("official_transcripts", "revoked_by_user_id") == "users.id"
    assert _foreign_key_target("assessment_scores", "institution_id") == "institutions.id"
    assert _foreign_key_target("assessment_scores", "assessment_component_id") == "assessment_components.id"
    assert _foreign_key_target("assessment_scores", "course_registration_id") == "course_registrations.id"
    assert _foreign_key_target("assessment_scores", "graded_by_user_id") == "users.id"
    assert _foreign_key_target("assessment_components", "institution_id") == "institutions.id"
    assert _foreign_key_target("assessment_components", "course_offering_id") == "course_offerings.id"
    assert _foreign_key_target("assessment_components", "lecturer_assignment_id") == "lecturer_assignments.id"
    assert _foreign_key_target("attendance_records", "institution_id") == "institutions.id"
    assert _foreign_key_target("attendance_records", "class_session_id") == "class_sessions.id"
    assert _foreign_key_target("attendance_records", "course_registration_id") == "course_registrations.id"
    assert _foreign_key_target("attendance_records", "recorded_by_user_id") == "users.id"
    assert _foreign_key_target("class_sessions", "institution_id") == "institutions.id"
    assert _foreign_key_target("class_sessions", "course_offering_id") == "course_offerings.id"
    assert _foreign_key_target("class_sessions", "lecturer_assignment_id") == "lecturer_assignments.id"
    assert _foreign_key_target("lecturer_assignments", "institution_id") == "institutions.id"
    assert _foreign_key_target("lecturer_assignments", "lecturer_id") == "lecturers.id"
    assert _foreign_key_target("lecturer_assignments", "course_offering_id") == "course_offerings.id"
    assert (
        _foreign_key_target("course_registrations", "institution_id")
        == "institutions.id"
    )
    assert (
        _foreign_key_target("course_registrations", "student_id")
        == "students.id"
    )
    assert (
        _foreign_key_target("course_registrations", "course_offering_id")
        == "course_offerings.id"
    )
    assert (
        _foreign_key_target("course_offerings", "institution_id")
        == "institutions.id"
    )
    assert _foreign_key_target("course_offerings", "course_id") == "courses.id"
    assert (
        _foreign_key_target("course_offerings", "academic_session_id")
        == "academic_sessions.id"
    )
    assert _foreign_key_target("course_offerings", "semester_id") == "semesters.id"
    assert _foreign_key_target("courses", "institution_id") == "institutions.id"
    assert _foreign_key_target("courses", "department_id") == "departments.id"
    assert _foreign_key_target("courses", "programme_id") == "programmes.id"
    assert (
        _foreign_key_target("courses", "academic_level_id")
        == "academic_levels.id"
    )
    assert (
        _foreign_key_target("academic_levels", "institution_id")
        == "institutions.id"
    )
    assert (
        _foreign_key_target("academic_levels", "programme_id")
        == "programmes.id"
    )
    assert (
        _foreign_key_target("institution_settings", "institution_id")
        == "institutions.id"
    )
    assert _foreign_key_target("users", "institution_id") == "institutions.id"
    assert _foreign_key_target("user_roles", "user_id") == "users.id"
    assert _foreign_key_target("user_roles", "role_id") == "roles.id"
    assert (
        _foreign_key_target("user_roles", "institution_id")
        == "institutions.id"
    )
    assert (
        _foreign_key_target("faculties", "institution_id") == "institutions.id"
    )
    assert (
        _foreign_key_target("departments", "institution_id")
        == "institutions.id"
    )
    assert (
        _foreign_key_target("departments", "faculty_id") == "faculties.id"
    )
    assert (
        _foreign_key_target("students", "institution_id") == "institutions.id"
    )
    assert _foreign_key_target("students", "user_id") == "users.id"
    assert (
        _foreign_key_target("lecturers", "institution_id") == "institutions.id"
    )
    assert _foreign_key_target("lecturers", "user_id") == "users.id"
    assert (
        _foreign_key_target("lecturers", "department_id") == "departments.id"
    )
    assert (
        _foreign_key_target("programmes", "institution_id")
        == "institutions.id"
    )
    assert _foreign_key_target("programmes", "faculty_id") == "faculties.id"
    assert (
        _foreign_key_target("programmes", "department_id") == "departments.id"
    )
    assert (
        _foreign_key_target("academic_sessions", "institution_id")
        == "institutions.id"
    )
    assert _foreign_key_target("semesters", "institution_id") == "institutions.id"
    assert _foreign_key_target("semesters", "academic_session_id") == "academic_sessions.id"
    assert (
        _foreign_key_target("audit_logs", "institution_id") == "institutions.id"
    )
    assert _foreign_key_target("audit_logs", "user_id") == "users.id"


def test_student_programme_reference_and_audit_timestamps() -> None:
    programme_id = Base.metadata.tables["students"].columns["programme_id"]
    assert next(iter(programme_id.foreign_keys)).target_fullname == "programmes.id"

    audit_log_columns = Base.metadata.tables["audit_logs"].columns
    assert "created_at" in audit_log_columns
    assert "updated_at" not in audit_log_columns
