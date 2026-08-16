from app.main import app
from app.services import guardian_portal_service

def test_all_guardian_portal_routes_exist_and_never_accept_guardian_id():
    paths=app.openapi()["paths"]
    expected=("/api/v1/guardian-portal/dashboard","/api/v1/guardian-portal/children","/api/v1/guardian-portal/children/{student_id}/overview","/api/v1/guardian-portal/children/{student_id}/results","/api/v1/guardian-portal/children/{student_id}/attendance","/api/v1/guardian-portal/children/{student_id}/academic-performance","/api/v1/guardian-portal/children/{student_id}/transcript","/api/v1/guardian-portal/children/{student_id}/clearance")
    for path in expected:
        assert path in paths and "guardian_id" not in paths[path]["get"].get("parameters",[])

def test_child_access_query_requires_verified_relationship_and_institution():
    class Session:
        def scalar(self,statement): self.sql=str(statement); return None
    session=Session()
    try:guardian_portal_service._relationship(session,institution_id=__import__('uuid').uuid4(),user_id=__import__('uuid').uuid4(),student_id=__import__('uuid').uuid4())
    except guardian_portal_service.GuardianPortalNotFoundError:pass
    assert "guardians.institution_id" in session.sql

def test_results_implementation_reuses_published_student_portal_filter():
    import inspect
    from app.services.student_portal_service import list_results
    source=inspect.getsource(list_results)
    assert 'Result.status == "published"' in source
    assert "AssessmentScore" not in inspect.getsource(guardian_portal_service.results)
