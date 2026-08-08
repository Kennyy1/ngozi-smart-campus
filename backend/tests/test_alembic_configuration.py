from pathlib import Path

import pytest
from alembic.config import Config

import app.models  # noqa: F401
from app.db.base import Base


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIRECTORY = BACKEND_ROOT / "alembic"
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
    "departments",
    "faculties",
    "examinations",
    "institution_settings",
    "institutions",
    "lecturers",
    "lecturer_assignments",
    "programmes",
    "roles",
    "semesters",
    "students",
    "user_roles",
    "users",
}


def test_alembic_structure_and_configuration() -> None:
    assert ALEMBIC_INI.is_file()
    assert (ALEMBIC_DIRECTORY / "env.py").is_file()
    assert (ALEMBIC_DIRECTORY / "script.py.mako").is_file()
    assert (ALEMBIC_DIRECTORY / "versions").is_dir()

    config = Config(str(ALEMBIC_INI))
    script_location = config.get_main_option("script_location")

    assert script_location is not None
    assert (BACKEND_ROOT / script_location).resolve() == ALEMBIC_DIRECTORY


def test_all_models_are_available_to_alembic() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_database_url_is_renderable_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEBUG", "false")
    from app.core.config import settings

    rendered_url = settings.DATABASE_URL.render_as_string(hide_password=False)

    assert rendered_url.startswith("postgresql+psycopg://")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
