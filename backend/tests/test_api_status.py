import pytest
import uuid
from fastapi.testclient import TestClient
from main import app
from models import AuditStatus

client = TestClient(app)

def test_get_audit_status_invalid_uuid():
    response = client.get("/api/v1/audit/invalid-uuid/status")
    assert response.status_code == 400
    assert "Invalid audit ID format" in response.text

def test_get_audit_status_not_found():
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/audit/{random_id}/status")
    assert response.status_code == 404
    assert "Audit not found" in response.text
