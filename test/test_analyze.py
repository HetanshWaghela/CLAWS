from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_analyze_invalid_file_type():
    files = {"pdf": ("note.txt", b"hello", "text/plain")}
    resp = client.post("/analyze", files=files)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Only PDF files are allowed"

def test_analyze_valid_file_type():
    fake_pdf = b"%PDF-1.4\n%EOF\n"
    files = {"pdf": ("sample.pdf", fake_pdf, "application/pdf")}
    resp = client.post("/analyze", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body and isinstance(body["job_id"], str)
    assert body["filename"]=="sample.pdf"
    