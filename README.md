# CLAWS — Contract Clause Mining & Review Copilot

CLAWS (Clause‑Law Assessment Workflow System) extracts, classifies, and reviews contract clauses at scale. It combines layout‑aware parsing, CUAD‑trained classifiers, retrieval‑augmented explanations, and an auditable API/UI.

---

## ✅ Explicit Choices (per project plan)

- **Datasets**: 
  - **CUAD** (Contract Understanding Atticus Dataset) — 41 clause labels across ~510 contracts for training/eval.
  - **DocLayNet** — large, human‑annotated layout dataset to recover page structure.
  - **Internal Policy KB** — short “risk explanation” notes per clause type (RAG context).
  - *(Optional)*: PubLayNet/DocBank only as augmentation for generic layout if needed.

- **Parsing (chosen after comparison)**: **PyMuPDF (fitz) + DocLayNet layout model**, with **Tesseract OCR** fallback for scanned PDFs.
  - See “Parsing choice & comparison” for why.

- **Models (aligned to CUAD + PDF)**:
  - **Clause classifier**: **roberta‑base** fine‑tuned on CUAD (multi‑label over segments).
  - **Layout**: **Aryn Deformable‑DETR (DocLayNet)** for block detection & reading order.
  - **Embeddings**: **sentence‑transformers/all‑MiniLM‑L6‑v2** for vector search over policy snippets.
  - **Q&A/Summarizer**: **Flan‑T5‑base** (CPU‑friendly) with strict RAG grounding.

- **Serving (production‑ready)**: **FastAPI packaged with BentoML** → Docker image → deploy on VM/K8s.
  - Alternative: pure FastAPI+Docker. See pros/cons below.

- **UI (fastest for you)**: **Gradio** MVP (file upload + clause list + Q&A). 
  - Alternative (later): **Next.js + PDF.js** reviewer for pixel‑accurate highlights.

- **Storage/Search**: Start with **SQLite + FAISS** (dev). Switch to **PostgreSQL + pgvector** (prod).
  - Toggle via `.env` and `configs/settings.py`.

- **Jobs**: **Celery + Redis** for async pipelines (ingest → mine → classify → score → report).

---

## 🏗️ Architecture

```
[Upload] -> [Parse (PyMuPDF + DocLayNet) -> OCR fallback] -> [Mine Clauses] -> [Classify (CUAD)]
      |                 |                                   |                   |
      v                 v                                   v                   v
  Storage        Layout blocks, offsets                 Vector store        Risk/Q&A (RAG)
      |                 |                                   |                   |
      +-----------------+---------------------> [FastAPI + BentoML] <-----------+
                                              -> /ui (Gradio)
```

---

## 📚 Parsing choice & comparison

**Goal:** robust text with correct reading order + coordinates, minimal effort, zero‑cost tooling.

| Tool              | Strengths                                                      | Weaknesses / Notes                             | Verdict |
|-------------------|----------------------------------------------------------------|------------------------------------------------|--------|
| **PyMuPDF (fitz)**| Fast, reliable text + char/word bboxes; images/pages easy.     | Needs custom ordering for multi‑column pages.  | **Use** (primary extractor) |
| pdfplumber        | Great table extraction; clear layout primitives.               | Slower; coordinate model differs per version.  | Keep for tables (optional) |
| pdfminer.six      | Very low‑level, battle‑tested.                                 | More glue code; slower for large PDFs.         | Backup only |
| GROBID            | Excellent for scholarly PDFs (TEI output).                     | Overkill for contracts; Java service.          | Skip for now |
| **Tesseract OCR** | Free OCR for scanned PDFs; configurable.                       | Quality varies; provisioning required.         | **Use** (scans fallback) |

**Final choice:** **PyMuPDF + DocLayNet layout detection**. We read text blocks & coordinates, use the layout model to order blocks (avoid footer/header/columns mix‑ups), and keep page/offset metadata for highlighting & citations. **Tesseract** runs only when a page lacks extractable text.

---

## 🧠 Models & Retrieval

- **Clause classifier**: fine‑tune `roberta-base` on CUAD as **multi‑label** segment classifier (41 heads or 1 head with sigmoid). Export to TorchScript/ONNX for speed.
- **Layout**: `Aryn/deformable-detr-DocLayNet` (Hugging Face) to detect block boxes & roles (text, title, list, table). We map text to boxes and preserve reading order.
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` for policy snippet vectors (tiny, fast, good enough).
- **RAG Q&A**: `google/flan-t5-base` with a strict prompt template that **always** includes (1) clause text, (2) policy snippet; post‑process to append contract + policy citations.
- **Guards**: refuse to answer beyond provided context; fall back to deterministic rules for risk flags.

It's an ongoing project.

