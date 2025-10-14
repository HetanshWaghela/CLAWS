from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_result_unknown_job():
    resp = client.get("/result/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown job_id"

def test_result_known_job():
    fake_pdf = b"%PDF-1.4\n%EOF\n"
    files = {"pdf": ("sample.pdf", fake_pdf, "application/pdf")}
    create = client.post("/analyze", files=files)
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    res = client.get(f"/result/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"] == job_id
    assert body["status"] == "done"
    assert isinstance(body["clauses"], list)
    assert len(body["clauses"]) >= 1

    c = body["clauses"][0]
    for key in ("type", "text", "page", "bbox", "score"):
        assert key in c