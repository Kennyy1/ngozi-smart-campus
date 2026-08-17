import inspect
import asyncio
from io import BytesIO
from pathlib import Path
import pytest

from app.main import app
from app.schemas.course_material import CourseMaterialCreate
from app.services import course_material_service as service
from app.services import course_material_storage as storage
from app.core.config import settings


def test_course_material_routes_and_authentication_exist():
    paths=app.openapi()["paths"]
    for path in ("/api/v1/course-materials","/api/v1/course-materials/{material_id}","/api/v1/course-materials/{material_id}/publish","/api/v1/course-materials/{material_id}/unpublish"):
        assert path in paths
    assert paths["/api/v1/course-materials"]["get"]["security"]
    assert "/api/v1/course-materials/upload" in paths
    assert "/api/v1/course-materials/{material_id}/download" in paths
    assert "multipart/form-data" in paths["/api/v1/course-materials/upload"]["post"]["requestBody"]["content"]


def test_external_url_metadata_is_validated_and_file_paths_are_not_accepted():
    value=CourseMaterialCreate(course_offering_id="00000000-0000-0000-0000-000000000001",title=" Note ",material_type="link",external_url="https://example.edu/note.pdf")
    assert value.title=="Note"
    assert "file_reference" not in CourseMaterialCreate.model_fields


def test_authorization_queries_enforce_assignment_registration_and_institution():
    lecturer=inspect.getsource(service._lecturer_assignment);student=inspect.getsource(service._student_registration)
    assert "LecturerAssignment.institution_id==institution_id" in lecturer
    assert 'LecturerAssignment.status=="active"' in lecturer
    assert "CourseRegistration.institution_id==institution_id" in student
    assert 'CourseRegistration.registration_status=="registered"' in student


def test_student_visibility_is_published_read_only_and_lecturer_write_is_owned():
    visible=inspect.getsource(service._visible);create=inspect.getsource(service.create)
    assert "item.is_published" in visible and "_student_registration" in visible
    assert "not write" in visible and '"lecturer" not in roles' in create
    assert "_lecturer_assignment" in create


def test_duplicate_and_publish_lifecycle_are_explicit():
    assert "DuplicateCourseMaterialError" in inspect.getsource(service.create)
    publish=inspect.getsource(service.publish)
    assert "published_at" in publish and "timezone.utc" in publish


def test_migration_has_complete_downgrade_and_no_binary_column():
    migration=(Path(__file__).parents[1]/"alembic/versions/d8a2f6c4b913_create_course_materials.py").read_text()
    assert 'down_revision="c1f4a8d2e607"' in migration
    assert 'op.drop_table("course_materials")' in migration
    assert "LargeBinary" not in migration


class _Upload:
    def __init__(self,name:str,content_type:str,content:bytes):self.filename=name;self.content_type=content_type;self.file=BytesIO(content)
    async def read(self,size:int=-1):return self.file.read(size)
    async def close(self):self.file.close()


def _upload(name: str, content_type: str, content: bytes) -> _Upload:
    return _Upload(name,content_type,content)


def test_valid_pdf_and_docx_are_stored_under_generated_references(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"COURSE_MATERIAL_STORAGE_DIR",tmp_path)
    pdf=asyncio.run(storage.store(_upload("../../Lecture Note.pdf","application/pdf",b"%PDF-safe")))
    docx=asyncio.run(storage.store(_upload("Week 1.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",b"PK-safe")))
    assert pdf.original_filename=="Lecture Note.pdf" and docx.original_filename=="Week 1.docx"
    assert "/" not in pdf.reference and "Lecture Note" not in pdf.reference
    assert storage.resolve(pdf.reference).read_bytes()==b"%PDF-safe"


def test_executable_and_oversized_uploads_are_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"COURSE_MATERIAL_STORAGE_DIR",tmp_path)
    with pytest.raises(storage.InvalidCourseMaterialFileError):asyncio.run(storage.store(_upload("malware.exe","application/octet-stream",b"MZ")))
    monkeypatch.setattr(settings,"COURSE_MATERIAL_MAX_UPLOAD_BYTES",4)
    with pytest.raises(storage.CourseMaterialFileTooLargeError):asyncio.run(storage.store(_upload("large.pdf","application/pdf",b"12345")))
    assert not list(tmp_path.iterdir())


def test_file_metadata_response_never_exposes_storage_reference_or_server_path():
    fields=set(__import__('app.schemas.course_material',fromlist=['CourseMaterialRead']).CourseMaterialRead.model_fields)
    assert "file_reference" not in fields and {"source_type","original_filename","mime_type","file_size"}<=fields
    source=inspect.getsource(service.download)
    assert "item=get(" in source and "resolve(item.file_reference)" in source


def test_uploaded_material_security_reuses_assignment_publication_and_registration_checks():
    uploaded=inspect.getsource(service.create_uploaded);visible=inspect.getsource(service._visible);deletion=inspect.getsource(service.delete)
    assert '"lecturer" not in roles' in uploaded and "_lecturer_assignment" in uploaded
    assert "item.is_published" in visible and "_student_registration" in visible
    assert "remove(reference)" in deletion


def test_upload_migration_extends_current_head_and_downgrades_all_metadata():
    migration=(Path(__file__).parents[1]/"alembic/versions/e5b7c9d1a204_extend_course_material_file_metadata.py").read_text()
    assert 'down_revision="d8a2f6c4b913"' in migration
    for field in ("source_type","original_filename","mime_type","file_size"):assert field in migration
    assert "LargeBinary" not in migration and "drop_column" in migration
