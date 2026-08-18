import asyncio,inspect
from datetime import datetime,timedelta,timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.main import app
from app.core.config import settings
from app.schemas.library import LibraryItemCreate,LoanCreate
from app.services import library_service as service
from app.services import library_storage as storage

class Upload:
    def __init__(self,name,mime,data):self.filename=name;self.content_type=mime;self.file=BytesIO(data)
    async def read(self,size=-1):return self.file.read(size)
    async def close(self):self.file.close()

def test_library_routes_are_authenticated_and_management_is_separate():
    paths=app.openapi()["paths"]
    for path in ("/api/v1/library/catalogue","/api/v1/library/catalogue/{item_id}","/api/v1/library/items","/api/v1/library/categories","/api/v1/library/authors","/api/v1/library/loans","/api/v1/library/my-loans","/api/v1/library/items/{item_id}/download"):
        assert path in paths
        assert next(iter(paths[path].values()))["security"]
    assert "multipart/form-data" in paths["/api/v1/library/items/{item_id}/upload"]["post"]["requestBody"]["content"]

def test_client_cannot_supply_storage_or_actor_metadata():
    fields=set(LibraryItemCreate.model_fields)
    assert not ({"file_reference","created_by_user_id","institution_id","sha256"}&fields)
    assert not ({"issued_by_user_id","institution_id"}&set(LoanCreate.model_fields))

def test_external_and_cover_urls_require_https():
    base=dict(title="Databases",item_type="ebook",access_type="digital")
    assert LibraryItemCreate(**base,external_url="https://library.example.edu/db.pdf").external_url
    with pytest.raises(ValidationError):LibraryItemCreate(**base,external_url="http://library.example.edu/db.pdf")

def test_file_storage_rejects_traversal_executable_empty_and_oversize(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"LIBRARY_RESOURCE_STORAGE_DIR",tmp_path)
    stored=asyncio.run(storage.store(Upload("../../reference.pdf","application/pdf",b"%PDF-safe")))
    assert stored.original_filename=="reference.pdf" and "/" not in stored.reference
    assert storage.resolve(stored.reference).parent==tmp_path.resolve()
    for upload in (Upload("run.exe","application/octet-stream",b"MZ"),Upload("empty.pdf","application/pdf",b""),Upload("fake.pdf","application/pdf",b"MZ executable")):
        with pytest.raises(storage.InvalidLibraryFile):asyncio.run(storage.store(upload))
    monkeypatch.setattr(settings,"LIBRARY_RESOURCE_MAX_UPLOAD_BYTES",5)
    with pytest.raises(storage.LibraryFileTooLarge):asyncio.run(storage.store(Upload("large.pdf","application/pdf",b"%PDF-too-large")))

def test_overdue_is_timezone_safe_and_returned_wins():
    now=datetime.now(timezone.utc);active=SimpleNamespace(due_at=now-timedelta(seconds=1),returned_at=None,status="borrowed")
    returned=SimpleNamespace(due_at=now-timedelta(days=10),returned_at=now,status="returned")
    boundary=SimpleNamespace(due_at=now,returned_at=None,status="borrowed")
    assert service.effective_status(active,now)=="overdue"
    assert service.effective_status(returned,now)=="returned"
    assert service.effective_status(boundary,now)=="borrowed"

def test_issue_and_return_are_actor_derived_and_copy_locked():
    issue=inspect.getsource(service.issue);returned=inspect.getsource(service.return_loan)
    assert "issued_by_user_id=actor_id" in issue and "with_for_update" in issue
    assert 'copy.status="borrowed"' in issue and "LIBRARY_STUDENT_LOAN_LIMIT" in issue and "LIBRARY_LECTURER_LOAN_LIMIT" in issue
    assert "returned_to_user_id=actor_id" in returned and 'copy.status="available"' in returned

def test_catalogue_and_loan_queries_are_institution_scoped():
    assert "LibraryItem.institution_id==institution_id" in inspect.getsource(service.catalogue)
    assert "LibraryLoan.institution_id==institution_id" in inspect.getsource(service.loans)
    assert "LibraryCopy.institution_id==institution_id" in inspect.getsource(service.issue)

def test_schema_and_migration_never_expose_or_store_binary_paths():
    from app.schemas.library import LibraryItemRead
    assert "file_reference" not in LibraryItemRead.model_fields and "sha256" not in LibraryItemRead.model_fields
    migration=(Path(__file__).parents[1]/"alembic/versions/b16d1f0a2026_create_digital_library.py").read_text()
    assert 'down_revision="a15c0e9f2026"' in migration
    assert "LargeBinary" not in migration
    for table in ("library_loans","library_copies","library_item_authors","library_items","authors","library_categories"):assert f'op.drop_table("{table}")' in migration
