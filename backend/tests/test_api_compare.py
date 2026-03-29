import pytest
from fastapi.testclient import TestClient
from main import app
from models import AuditStatus

client = TestClient(app)

def test_compare_endpoint_validation():
    # Test valid request
    response = client.post(
        "/api/v1/compare",
        json={"urls": ["https://github.com/owner/repo1", "https://github.com/owner/repo2"]}
    )
    # Just asserting it didn't fail validation
    assert response.status_code in (200, 400, 502)

def test_compare_endpoint_too_many_urls():
    response = client.post(
        "/api/v1/compare",
        json={"urls": [
            "https://github.com/owner/repo1",
            "https://github.com/owner/repo2",
            "https://github.com/owner/repo3",
            "https://github.com/owner/repo4",
            "https://github.com/owner/repo5",
            "https://github.com/owner/repo6",
        ]}
    )
    assert response.status_code == 422
    assert "too_long" in response.text

def test_compare_endpoint_invalid_url():
    response = client.post(
        "/api/v1/compare",
        json={"urls": ["https://github.com/owner/repo1", "not-a-url"]}
    )
    assert response.status_code == 422
    assert "Invalid GitHub URL" in response.text

def test_compare_endpoint_empty_urls():
    response = client.post(
        "/api/v1/compare",
        json={"urls": []}
    )
    assert response.status_code == 422
    assert "too_short" in response.text
