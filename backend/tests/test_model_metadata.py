from sqlalchemy import UniqueConstraint

import app.models  # noqa: F401
from app.db.base import Base


EXPECTED_TABLES = {
    "academic_levels",
    "academic_sessions",
    "audit_logs",
    "courses",
    "course_offerings",
    "departments",
    "faculties",
    "institutions",
    "institution_settings",
    "lecturers",
    "programmes",
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


def test_expected_unique_constraints() -> None:
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


def test_deferred_programme_reference_and_audit_timestamps() -> None:
    programme_id = Base.metadata.tables["students"].columns["programme_id"]
    assert not programme_id.foreign_keys

    audit_log_columns = Base.metadata.tables["audit_logs"].columns
    assert "created_at" in audit_log_columns
    assert "updated_at" not in audit_log_columns
