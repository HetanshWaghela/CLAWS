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
from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
from app.llm_generator import get_llm_generator
# CUAD model removed - using rule-based legal detection instead


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
    color: str

class QARequest(BaseModel):
    question: str
    job_id: str

class QAResponse(BaseModel):
    answer: str
    clause_text: str = ""
    clause_type: str = ""
    page: int = 0



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
   
    highlighted_pdf_path = data_dir() / "uploads" / f"{job_id}_highlighted.pdf"
    original_pdf_path = data_dir() / "uploads" / f"{job_id}.pdf"
    
    if highlighted_pdf_path.exists():
        print(f"📄 Serving highlighted PDF: {highlighted_pdf_path}")
        return FileResponse(
            str(highlighted_pdf_path),
            media_type="application/pdf",
            filename=f"{job_id}_highlighted.pdf",
            headers={"Content-Disposition": f"inline; filename={job_id}_highlighted.pdf"}
        )
    elif original_pdf_path.exists():
        print(f"📄 Serving original PDF: {original_pdf_path}")
        return FileResponse(
            str(original_pdf_path),
            media_type="application/pdf",
            filename=f"{job_id}.pdf",
            headers={"Content-Disposition": f"inline; filename={job_id}.pdf"}
        )
    else:
        raise HTTPException(status_code=404, detail="PDF not found")
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

@app.post("/explain", response_model=QAResponse)
def explain_clause(request: QARequest):
    try:
        clause_type = parse_question(request.question)
        
        result_path = data_dir() / "results" / f"{request.job_id}.json"
        if not result_path.exists():
            return QAResponse(answer="No contract analysis found. Please upload and analyze a contract first.")
        
        with open(result_path, 'r') as f:
            result_data = json.load(f)
        
        detected_clauses = result_data.get('clauses', [])
        
        if clause_type == 'GENERAL_CONTRACT':
            answer = generate_contract_summary(detected_clauses, request.question)
            return QAResponse(
                answer=answer,
                clause_text="",
                clause_type="General Contract",
                page=0
            )
        
       
        elif clause_type == 'GENERAL_QUESTION':
            if detected_clauses:
             
                context = "Contract clauses detected:\n"
                for clause in detected_clauses[:10]:  
                    context += f"- {clause.get('type', 'Unknown')}: {clause.get('text', '')[:100]}...\n"
                
                llm_generator = get_llm_generator()
                prompt = f"{context}\n\nQuestion: {request.question}\n\nAnswer:"
                answer = llm_generator.generate_explanation(prompt, request.question)
                
                if answer and answer != "No explanation available":
                    return QAResponse(
                        answer=answer,
                        clause_text="",
                        clause_type="General Question",
                        page=0
                    )
                else:
                    return QAResponse(
                        answer="I can help you understand this contract. Try asking about specific clauses like 'What are the risks with the assignment clause?' or 'Tell me about the termination clause.'",
                        clause_text="",
                        clause_type="General Question",
                        page=0
                    )
            else:
                return QAResponse(
                    answer="No contract clauses were detected. Please ensure the contract was properly analyzed.",
                    clause_text="",
                    clause_type="General Question",
                    page=0
                )
        
        elif clause_type:
            clause = retrieve_clause(clause_type, detected_clauses)
            policy = get_policy_explanation(clause_type)
            
            if not policy:
                
                clause_text = clause['text'] if clause else ""
                if clause_text:
                    llm_generator = get_llm_generator()
                    llm_answer = llm_generator.generate_explanation(clause_text, request.question)
                    if llm_answer != "No explanation available":
                        answer = f"LLM Analysis: {llm_answer}"
                    else:
                        answer = f"No risk information available for {clause_type} clauses."
                else:
                    answer = f"No {clause_type} clause found in the contract."
            else:
                clause_text = clause['text'] if clause else ""
                answer = generate_answer(clause_text, policy, request.question)
            
            clause_page = clause['page'] if clause else 0
            
            return QAResponse(
                answer=answer,
                clause_text=clause_text,
                clause_type=clause_type,
                page=clause_page
            )
        
        else:
            return QAResponse(
                answer="I can help you understand this contract. Try asking about specific clauses or general questions like 'What is this contract about?'",
                clause_text="",
                clause_type="Unknown",
                page=0
            )
            
    except Exception as e:
        return QAResponse(answer=f"Error processing question: {str(e)}")


@app.on_event("startup")
def _start_worker():
    print("Starting CLAWS with rule-based legal detection")
    print("RoBERTa legal Q&A model will load on first use")
    t= Thread(target= _worker, daemon= True)
    t.start()



