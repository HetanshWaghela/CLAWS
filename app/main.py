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

class Annotation(BaseModel):
    id: str
    page: int
    bbox: list[float]
    color: str= "rgba(255,230,0,0.35)"
    label: str|None =None

class AnnotationRequest(BaseModel):
    action: str #add, update, delete
    annotation: Annotation | None = None
    id: str | None = None

class PdfRectItem(BaseModel):
    page: int
    rect: list[float]  # [x1,y1,x2,y2] in PDF points
    color: str | None = None

class AnnotatePayload(BaseModel):
    items: list[PdfRectItem]

class HighlightTextRequest(BaseModel):
    page: int
    text: str
    color: str | None = None



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

def __ann_path(job_id: str) -> Path:
    return data_dir() / "annotations" / f"{job_id}.annoatations.json"

def _read_annotations(job_id: str) -> list[dict]:
    p = __ann_path(job_id)
    if not p.exists():
        return []
    return json.loads(p.read_text() or "[]")

def _write_annotations(job_id: str, items: list[dict]) -> None:
    p = __ann_path(job_id)
    p.parent.mkdir(parents= True, exist_ok = True)
    p.write_text(json.dumps(items))

def _rgba_to_components(rgba: str) -> tuple[float,float,float,float]:
    try:
        s = rgba.strip().lower().replace('rgba(','').replace(')','')
        parts = [float(x.strip()) for x in s.split(',')]
        if len(parts)==4:
            r,g,b,a = parts
            return r/255.0, g/255.0, b/255.0, a
    except Exception:
        pass
    return 1.0, 1.0, 0.0, 0.35



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

@app.post("/highlight_text/{job_id}")
def highlight_text(job_id: str, req: HighlightTextRequest):
    pdf_path = data_dir() / "uploads" / f"{job_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Unknown job_id")
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to open PDF")
    try:
        idx = max(0, req.page - 1)
        if idx >= len(doc):
            raise HTTPException(status_code=400, detail="Invalid page")
        page = doc[idx]
        rects = page.search_for(req.text or "")
        if not rects:
            return {"status": "not_found"}
        r,g,b,a = _rgba_to_components(req.color or "rgba(255,230,0,0.35)")
        for rect in rects:
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=(r,g,b))
            annot.set_opacity(a)
            annot.update()
        doc.saveIncr()
        return {"status": "ok", "count": len(rects)}
    finally:
        doc.close()

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
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/annotations/{job_id}")
def get_annotations(job_id: str):
    if _read_result(job_id) is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return {"items": _read_annotations(job_id)}

@app.post("/annotations/{job_id}")
def post_annotations(job_id: str, request: AnnotationRequest):
    if _read_result(job_id) is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    items= _read_annotations(job_id)
    if request.action == "add" and request.annotation:
        if any(it.get("id") == request.annotation.id for it in items):
            raise HTTPException(status_code=400, detail="Duplicate annotation ID")
        items.append(request.annotation.model_dump())
    elif request.action == "update" and request.annotation:
        items =[request.annotation.model_dump() if it.get("id")==request.annotation.id else it for it in items]
    elif request.action == "delete" and request.id:
        items = [it for it in items if it.get("id")!=request.id]
    else:
        raise HTTPException(status_code=400, detail="Invalid request")
    _write_annotations(job_id, items)
    return {"items": items}

@app.post("/annotate_pdf/{job_id}")
def annotate_pdf(job_id: str, payload: AnnotatePayload):
    pdf_path = data_dir() / "uploads" / f"{job_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Unknown job_id")
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to open PDF")
    try:
        for it in payload.items:
            idx = max(0, it.page - 1)
            if idx >= len(doc):
                continue
            page = doc[idx]
            x1,y1,x2,y2 = it.rect
            rect = fitz.Rect(float(x1), float(y1), float(x2), float(y2))
            r,g,b,a = _rgba_to_components(it.color or "rgba(255,230,0,0.35)")
            annot = page.add_rect_annot(rect)
            annot.set_colors(fill=(r,g,b), stroke=(r,g,b))
            annot.set_opacity(a)
            annot.update()
        doc.saveIncr()
    finally:
        doc.close()
    return {"status": "ok"}



