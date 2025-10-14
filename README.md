# CLAWS 

CLAWS (Clause‑Law Assessment Workflow System) helps legal teams review contracts faster by automatically extracting key clauses, highlighting them on the PDF, and generating grounded, explainable risk summaries with citations. This project prioritizes privacy (local models), auditability (page/bbox citations), and production‑ready architecture.

---

## Why it matters

- Speed up due diligence on NDAs/MSAs and similar agreements
- Identify 40+ clause types (CUAD) with locations for highlight/review
- Provide short, grounded “why it’s risky” explanations with citations

---

## High‑level workflow

1. Upload PDF (contract)
2. Layout‑aware parsing → text blocks with page and bounding boxes
3. Clause detection (baseline rules → CUAD fine‑tuned model)
4. Persist results (clauses with type, text, page, bbox, score)
5. Q&A/Risk explanation via RAG (contract span + policy snippet) with citations

---

## Datasets & knowledge

- CUAD (Contract Understanding Atticus Dataset): 41 clause categories; ~13k annotations across ~510 contracts
- DocLayNet: layout segmentation to preserve reading order and coordinates
- Internal Policy/KB: short per‑clause “risk explanation” snippets used for RAG

---

## Architecture (MVP → Production)

```
[Upload] -> [Parse (PyMuPDF + layout) -> OCR fallback] -> [Detect Clauses]
      |                |                              |            
      v                v                              v            
  Storage        Blocks w/ page+bbox               Vector/RAG     
      |                |                              |            
      +----------------+--------------> [FastAPI] <---+            
                                     -> /ui (Gradio)
```

- Parsing: PyMuPDF for text and coordinates; upgrade path to DocLayNet layout model; OCR fallback for scans (later)
- Clause detection: start with keyword heuristics; upgrade to RoBERTa/DistilBERT multi‑label model trained on CUAD
- RAG explanations: local Flan‑T5‑Base (or similar) with strict grounding to contract span and policy snippet
- Storage: filesystem JSON for MVP; upgrade to SQLite/PostgreSQL
- Serving: FastAPI; background worker for async processing

---

## Current API (MVP)

- GET `/healthz` → `{ "status": "ok" }`
- POST `/analyze` (multipart form field `pdf`) → `{ job_id, filename, status: "queued" }`
- GET `/result/{job_id}` → `{ job_id, status: "queued|processing|done|error", clauses: [ { type, text, page, bbox, score } ] }`

Notes:
- Uploads: `data/uploads/{job_id}.pdf`
- Results: `data/results/{job_id}.json`
- `DATA_DIR` env var can override `data`

---

## Data model (responses)

- AnalyzeResponse: `{ job_id: str, filename: str, status: str }`
- Clause: `{ type: str, text: str, page: int, bbox: [x0,y0,x1,y1], score: float }`
- Result: `{ job_id: str, status: str, clauses: Clause[] }`

---

## Local development

Prereqs: Python 3.11+

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Tests:
```bash
pytest -q
```

Generated files are ignored via `.gitignore`. You can redirect storage with `DATA_DIR=/tmp/claws`.

---

## Implementation roadmap (from claws_info.txt)

1) Parsing & layout
- Use PyMuPDF to extract blocks (text + page/bbox) in reading order
- Upgrade: DocLayNet layout model to robustly handle multi‑column, headers/footers, tables
- OCR fallback for scanned PDFs (later)

2) Clause detection
- Baseline: keyword heuristics (e.g., “governed by the laws of” → Governing Law; “indemnify/hold harmless” → Indemnity)
- Model: fine‑tune RoBERTa/DistilBERT on CUAD for multi‑label classification of blocks
- Export/optimize: ONNX/quantization for CPU latency

3) RAG explanations
- Policy KB: short snippets per clause type (plain text/JSON)
- Endpoint `/explain`: take `{ job_id, clause_type }`, compose prompt with contract span + policy snippet, generate a grounded 3–5 sentence explanation with citations `[Contract p.X] [Policy Y]`
- Local LLM (Flan‑T5‑Base or similar); strict guardrails to avoid hallucinations

4) Backend & UI
- Async jobs: queued → processing → done; worker persists results for `/result/{job_id}`
- UI MVP (Gradio): upload, list clauses, render page image with bbox highlight
- Upgrade UI: React + PDF.js for pixel‑perfect overlay and navigation

5) Storage & MLOps
- MVP: filesystem JSON; Upgrade: SQLite → Postgres (pgvector optional)
- CI/CD: lint/type‑check/tests; containerize and deploy to a small VM
- Tracking: optional DVC (datasets/models) and MLflow (experiments)

6) Security & compliance (baseline)
- Local‑only processing by default; clear warnings if data would leave machine
- Upload size limits; MIME sniffing; optional virus scan
- Auth/TLS added before any public deployment

---

## Acceptance targets (guidance)

- Accuracy: ≥0.80 macro‑F1 overall; high precision on risky clauses
- Latency (CPU): parse+detect ≤15s for ~30 pages; explain ≤2s
- Reliability: no crashes on batch uploads; 100% answers carry citations

---

## Project status

MVP backend in progress:
- Endpoints implemented (`/healthz`, `/analyze`, `/result`)
- Real parsing via PyMuPDF with async worker and JSON persistence
- Tests for health, upload validation, and async result polling

Next suggested tracks:
- Add baseline clause heuristics → swap to CUAD model
- Introduce `/explain` with a tiny policy KB
- Gradio UI for clause listing and highlight previews

---

## License

This repository is for educational/demo purposes. Verify dataset/model licenses (e.g., CUAD, DocLayNet) before redistribution.


