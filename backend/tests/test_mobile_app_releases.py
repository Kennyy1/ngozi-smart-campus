import asyncio,hashlib,inspect
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import pytest
from app.core.config import settings
from app.main import app
from app.models.mobile_app_release import MobileAppRelease
from app.schemas.mobile_app_release import MobileReleaseRead,PublicMobileRelease
from app.services import mobile_app_release_service as service
from app.services import mobile_release_storage as storage

class Upload:
    def __init__(self,name,content=b"APK",content_type="application/vnd.android.package-archive"):self.filename=name;self.content_type=content_type;self.file=BytesIO(content)
    async def read(self,size=-1):return self.file.read(size)
    async def close(self):self.file.close()
def test_routes_are_public_or_admin_as_required():
    paths=app.openapi()["paths"]
    assert not paths["/api/v1/public/mobile-app/android/latest"]["get"].get("security")
    assert not paths["/api/v1/public/mobile-app/android/download"]["get"].get("security")
    for path,method in [("/api/v1/mobile-app-releases/upload","post"),("/api/v1/mobile-app-releases","get"),("/api/v1/mobile-app-releases/{release_id}/publish","post"),("/api/v1/mobile-app-releases/{release_id}/retire","post")]:assert paths[path][method]["security"]
    assert "multipart/form-data" in paths["/api/v1/mobile-app-releases/upload"]["post"]["requestBody"]["content"]
def test_valid_apk_is_safely_stored_with_server_metadata(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"MOBILE_RELEASE_STORAGE_DIR",tmp_path);content=b"PK\x03\x04real-apk-payload"
    result=asyncio.run(storage.store(Upload("../../unsafe name.apk",content)))
    assert result.original_filename=="unsafe name.apk" and "/" not in result.reference and result.reference.endswith(".apk")
    assert result.size==len(content) and result.sha256==hashlib.sha256(content).hexdigest() and storage.resolve(result.reference).read_bytes()==content
def test_invalid_empty_and_oversized_apks_are_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"MOBILE_RELEASE_STORAGE_DIR",tmp_path)
    with pytest.raises(storage.InvalidMobileReleaseFileError):asyncio.run(storage.store(Upload("file.txt")))
    with pytest.raises(storage.InvalidMobileReleaseFileError):asyncio.run(storage.store(Upload("empty.apk",b"")))
    monkeypatch.setattr(settings,"MOBILE_RELEASE_MAX_UPLOAD_BYTES",2)
    with pytest.raises(storage.MobileReleaseFileTooLargeError):asyncio.run(storage.store(Upload("large.apk",b"123")))
    assert not list(tmp_path.iterdir())
def test_metadata_is_global_unique_and_contains_no_apk_binary():
    table=MobileAppRelease.__table__;unique={tuple(c.name for c in x.columns) for x in table.constraints if x.__class__.__name__=="UniqueConstraint"}
    assert ("platform","version") in unique and ("platform","version_code") in unique
    assert "institution_id" not in table.c and all("BLOB" not in str(c.type).upper() and "BINARY" not in str(c.type).upper() for c in table.c)
def test_public_schema_omits_internal_and_actor_fields():
    fields=set(PublicMobileRelease.model_fields);assert {"file_reference","created_by_user_id","id","status","is_latest"}.isdisjoint(fields)
    assert {"version","version_code","filename","file_size","sha256","release_notes","released_at","download_url"}<=fields
    assert "file_reference" not in MobileReleaseRead.model_fields
def test_lifecycle_and_latest_queries_are_explicit():
    publish=inspect.getsource(service.publish);latest=inspect.getsource(service.latest);download=inspect.getsource(service.download)
    assert "values(is_latest=False)" in publish and 'item.status="published"' in publish and "timezone.utc" in publish
    assert 'status=="published"' in latest and "is_latest.is_(True)" in latest
    assert 'status=="published"' in download and "resolve(item.file_reference)" in download
def test_public_filename_is_versioned_and_unknown_release_is_safe():
    assert service.public_filename("1.0.0")=="ngozi-smart-campus-android-v1.0.0.apk"
    class Session:
        def scalar(self,_):return None
    with pytest.raises(service.MobileReleaseNotFoundError):service.latest(Session())
def test_migration_is_single_complete_successor():
    source=(Path(__file__).parents[1]/"alembic/versions/f9d2a6c4b817_create_mobile_app_releases.py").read_text()
    assert 'down_revision:str|Sequence[str]|None="e5b7c9d1a204"' in source and 'op.drop_table("mobile_app_releases")' in source
    for value in ["platform","version_code","sha256","released_at","created_by_user_id","uq_mobile_app_releases_latest_platform"]:assert value in source
    assert "LargeBinary" not in source
