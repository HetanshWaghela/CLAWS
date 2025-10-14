from fastapi.testclient import TestClient
from app.main import app
import time

client = TestClient(app)

def test_result_unknown_job():
    resp = client.get("/result/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown job_id"

def test_result_known_job():
    fake_pdf = b"%PDF-1.4\n%EOF\n"
    files = {"pdf": ("sample.pdf", fake_pdf, "application/pdf")}

    with TestClient(app) as client:
        create = client.post("/analyze", files=files)
        assert create.status_code == 200
        job_id = create.json()["job_id"]

        last_status = None
        
        for _ in range(200):  
            res = client.get(f"/result/{job_id}")
            assert res.status_code == 200
            body = res.json()
            last_status = body.get("status")
            if last_status == "done":
                assert isinstance(body["clauses"], list)
                return
            time.sleep(0.05)

        raise AssertionError(f"Job did not reach done status within timeout (last status={last_status})")