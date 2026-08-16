from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.main import app
from app.models.guardian import Guardian
from app.models.guardian_student import GuardianStudent
from app.schemas.guardian import GuardianCreate,GuardianStudentCreate,GuardianStudentUpdate
from app.services.role_assignment_service import GUARDIAN_ROLE

def test_guardian_create_contract_is_secure_and_conservative():
    value=GuardianCreate(email="parent@example.edu",password="ChangeMe123!",first_name="Ada",last_name="Parent")
    assert value.email=="parent@example.edu" and GUARDIAN_ROLE=="guardian"
    assert {"institution_id","user_id","password_hash","is_active"}.isdisjoint(GuardianCreate.model_fields)
    with pytest.raises(ValidationError):GuardianCreate(email="parent@example.edu",password="short",first_name="Ada",last_name="Parent")

def test_relationship_creation_cannot_self_verify_or_select_institution():
    value=GuardianStudentCreate(guardian_id=uuid4(),student_id=uuid4(),relationship_type="mother")
    assert not any((value.can_view_results,value.can_view_attendance,value.can_view_academic_performance,value.can_view_transcript,value.can_view_clearance))
    assert {"institution_id","status","created_at","updated_at"}.isdisjoint(GuardianStudentCreate.model_fields)
    assert "status" not in GuardianStudentUpdate.model_fields

def test_guardian_models_are_institution_scoped_and_historical():
    assert {"institution_id","user_id","is_active"}<=set(Guardian.__table__.columns.keys())
    assert {"institution_id","guardian_id","student_id","status"}<=set(GuardianStudent.__table__.columns.keys())
    assert "DELETE" not in {route.methods.pop() for route in app.routes if getattr(route,"path","").endswith("guardian-student-relationships/{relationship_id}") and route.methods}

def test_management_and_lifecycle_routes_are_registered():
    paths=app.openapi()["paths"]
    for path in ("/api/v1/guardians","/api/v1/guardian-student-relationships","/api/v1/guardian-student-relationships/{relationship_id}/verify","/api/v1/guardian-student-relationships/{relationship_id}/suspend","/api/v1/guardian-student-relationships/{relationship_id}/revoke"):
        assert path in paths
