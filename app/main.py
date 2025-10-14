from fastapi import FastAPI,UploadFile, HTTPException
from uuid import uuid4
from pydantic import BaseModel
from pathlib import Path
import json
from app.parser import parse_pdf

app = FastAPI()

class AnalyzeResponse(BaseModel):
    job_id: str
    filename: str

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


@app.get("/healthz")
def health_check():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(pdf:UploadFile):
    if pdf.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    job_id= str(uuid4())
    uploads= Path("data/uploads")
    uploads.mkdir(parents= True, exist_ok= True)
    dest= uploads/ f"{job_id}.pdf"
    dest.write_bytes(await pdf.read())
    clauses= parse_pdf(str(dest))
    results_dir = Path("data/results")
    results_dir.mkdir(parents= True, exist_ok= True)
    stub= Result(job_id=job_id, status="done",clauses=clauses)
    (results_dir/ f"{job_id}.json").write_text(stub.model_dump_json())
    return AnalyzeResponse(job_id=job_id, filename=pdf.filename)

@app.get("/result/{job_id}")
def get_result(job_id: str):
    path = Path("data/results") / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return json.loads(path.read_text())

#we implement the stub(parser.py)





