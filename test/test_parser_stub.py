from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)
 
def test_analyze_then_result_includes_stub_clauses():
    fake_pdf = b"%PDF-1.4\n%EOF\n"
    files = {"pdf": ("sample.pdf", fake_pdf, "application/pdf")}
    resp= client.post("/analyze", files=files)
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    res = client.get(f"/result/{job_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "done"
    assert isinstance(body["clauses"], list)
    assert len(body["clauses"]) >= 1

    c = body["clauses"][0]
    for key in ("type", "text", "page", "bbox", "score"):
        assert key in c

    assert isinstance(c["type"], str)
    assert isinstance(c["text"], str)
    assert isinstance(c["page"], int)
    assert isinstance(c["bbox"], list) and len(c["bbox"]) == 4
    assert all(isinstance(v, (int, float)) for v in c["bbox"])
    assert isinstance(c["score"], (int, float))