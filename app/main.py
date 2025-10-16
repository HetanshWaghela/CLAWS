from fastapi import FastAPI,UploadFile, HTTPException, Response
from fastapi.responses import FileResponse
from uuid import uuid4
from pydantic import BaseModel
from pathlib import Path
import time
import os
import queue
from threading import Thread
import json
import fitz
from app.parser import parse_pdf


app = FastAPI()

class AnalyzeResponse(BaseModel):
    job_id: str
    filename: str
    status: str

class Clause(BaseModel):
    type: str
    text: str
    page: int
    bbox : list[float]
    score : float

class Result(BaseModel):
    job_id: str
    status: str
    clauses: list[Clause] = []

def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))

_job_q: "queue.Queue[tuple[str, Path]]" = queue.Queue() 
def _write_result(obj: Result) -> None:
    results_dir=data_dir() / "results"
    results_dir.mkdir(parents= True, exist_ok = True)
    (results_dir/ f"{obj.job_id}.json").write_text(obj.model_dump_json())

def _read_result(job_id: str) -> dict | None:
    path= data_dir()/ "results"/ f"{job_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text() or "{}")

def _worker():
    while True:
        try:
            job_id, pdf_path = _job_q.get()
            _write_result(Result(job_id=job_id, status="processing",clauses=[]))
            clauses= parse_pdf(str(pdf_path))
            _write_result(Result(job_id=job_id, status="done",clauses=clauses))
        except Exception as e:
            _write_result(Result(job_id=job_id, status="error",clauses=[]))
            print(f"Error processing job {job_id}: {e}")
        finally:
            _job_q.task_done()
            time.sleep(0.01)

@app.on_event("startup")
def _start_worker():
    t= Thread(target= _worker, daemon= True)
    t.start()


@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(pdf:UploadFile):
    if pdf.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    job_id= str(uuid4())
    base= data_dir()
    uploads= base/ "uploads"
    uploads.mkdir(parents= True, exist_ok= True)
    dest= uploads/ f"{job_id}.pdf"
    dest.write_bytes(await pdf.read())
    _write_result(Result(job_id=job_id, status="queued",clauses=[]))
    _job_q.put((job_id, dest))
    return AnalyzeResponse(job_id=job_id, filename=pdf.filename, status="queued")

@app.get("/result/{job_id}")
def get_result(job_id: str):
    data = _read_result(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return data

@app.get("/pdf/{job_id}")
def get_pdf(job_id: str):
    pdf_path= data_dir() / "uploads" / f"{job_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"{job_id}.pdf",
        headers={"Content-Disposition": f"inline; filename={job_id}.pdf"}
        )

