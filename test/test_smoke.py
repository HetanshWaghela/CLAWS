from fastapi.testclient import TestClient
from app.main import app


def test_ping():
    c = TestClient(app)
    assert c.get("/ping").json()["status"] == "ok"


def test_explain_requires_text():
    c = TestClient(app)
    r = c.post("/explain", json={"question": ""})
    assert r.status_code == 422


def test_explain_stub_ok():
    c = TestClient(app)
    got = c.post("/explain", json={"question": "Why is assignment risky?"}).json()
    assert "Stub" in got["answer"]
    assert got["citations"]
