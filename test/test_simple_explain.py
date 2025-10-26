import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_explain_no_job_id():
    """Test explain endpoint with non-existent job ID."""
    response = client.post("/explain", json={
        "question": "What is this contract about?",
        "job_id": "non-existent-job-id"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "No contract analysis found" in data["answer"]

def test_explain_invalid_json():
    """Test explain endpoint with invalid JSON."""
    response = client.post("/explain", json={
        "question": "What is this contract about?"
        # Missing job_id
    })
    
    assert response.status_code == 422  # Validation error

def test_explain_empty_question():
    """Test explain endpoint with empty question."""
    response = client.post("/explain", json={
        "question": "",
        "job_id": "test-job-789"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data

def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
