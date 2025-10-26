"""
CLAWS - Streamlit App with Backend (Exact copy of ui/app.py approach)
This version creates a simple backend to serve PDFs like the original ui/app.py
"""

import streamlit as st
import tempfile
import os
import base64
import threading
import time
from pathlib import Path
from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
from app.parser import parse_pdf
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import requests

# Global variables for backend
backend_running = False
pdf_path = None
clauses_data = None

# Create FastAPI backend
app = FastAPI()

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}

@app.get("/pdf/{job_id}")
async def get_pdf(job_id: str):
    global pdf_path
    if pdf_path and os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf")
    return {"error": "PDF not found"}

@app.post("/analyze")
async def analyze_pdf(pdf: UploadFile = File(...)):
    global pdf_path, clauses_data
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        content = await pdf.read()
        tmp_file.write(content)
        pdf_path = tmp_file.name
    
    # Process PDF
    clauses_data = parse_pdf(pdf_path)
    
    return {"job_id": "streamlit_job", "filename": pdf.filename, "status": "done"}

@app.get("/result/{job_id}")
async def get_result(job_id: str):
    global clauses_data
    if clauses_data is not None:
        return {"job_id": job_id, "status": "done", "clauses": clauses_data}
    return {"job_id": job_id, "status": "processing", "clauses": []}

@app.post("/explain")
async def explain_clause(request):
    question = request.get("question", "")
    job_id = request.get("job_id", "")
    
    if not clauses_data:
        return {"answer": "No contract data available", "clause_text": "", "clause_type": "", "page": 0}
    
    # Parse question
    question_type = parse_question(question)
    
    if question_type == 'GENERAL_CONTRACT':
        answer = generate_contract_summary(clauses_data, question)
        return {"answer": answer, "clause_text": "", "clause_type": "GENERAL_CONTRACT", "page": 0}
    else:
        # Find relevant clause
        clause = retrieve_clause(question_type, clauses_data)
        if clause:
            policy = get_policy_explanation(question_type)
            answer = generate_answer(clause['text'], policy, question)
            return {
                "answer": answer, 
                "clause_text": clause['text'], 
                "clause_type": clause['type'], 
                "page": clause['page']
            }
        else:
            return {"answer": "No relevant clause found", "clause_text": "", "clause_type": "", "page": 0}

def start_backend():
    global backend_running
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
        backend_running = True
    except Exception as e:
        print(f"Backend error: {e}")

# Start backend in background
if not backend_running:
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()
    time.sleep(2)  # Give backend time to start

# Streamlit UI (exact copy from ui/app.py)
st.set_page_config(page_title="CLAWS", layout="wide")
st.title("CLAWS - Clause Law Assessment Workflow System")

st.sidebar.header("Upload PDF")
uploaded = st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])

API_BASE = "http://localhost:8000"

if uploaded is not None:
    files = {"pdf": (uploaded.name, uploaded.getvalue(), "application/pdf")}
    with st.spinner("Uploading and queueing.."):
        try:
            resp = requests.post(f"{API_BASE}/analyze", files=files, timeout=120)
            resp.raise_for_status()
        except Exception as e:
            st.error(f"Failed to upload: {e}")
            st.stop()
    data = resp.json()
    job_id = resp.json()["job_id"]
    status = data.get("status")
    st.success(f"Uploaded and queued job {job_id} ({status})")

    placeholder = st.empty()
    last_status = status
    for _ in range(200):
        try:
            r = requests.get(f"{API_BASE}/result/{job_id}", timeout=60)
            if r.status_code == 404:
                placeholder.warning("Unknown job_id. Retrying...")
                time.sleep(0.2)
                continue
            r.raise_for_status()
        except Exception as e:
            placeholder.error(f"Polling failed: {e}")
            time.sleep(0.2)
            continue

        body = r.json()
        last_status = body.get("status")
        placeholder.info(f"Current status: {last_status}")

        if last_status == "done":
            clauses = body.get("clauses", [])
            
            st.markdown("---")
            st.subheader("🤖 Legal Q&A")
            st.write("Ask questions about detected clauses and their risks:")
            
            question = st.text_input("Ask a question about the contract:", placeholder="e.g., Why is the assignment clause risky?")
            
            if st.button("Get Answer") and question:
                with st.spinner("Analyzing question..."):
                    try:
                        qa_response = requests.post(f"{API_BASE}/explain", 
                            json={"question": question, "job_id": job_id}, 
                            timeout=30)
                        qa_response.raise_for_status()
                        qa_data = qa_response.json()
                        
                        st.markdown("### Answer:")
                        st.write(qa_data['answer'])
                        
                        if qa_data.get('clause_text'):
                            st.markdown("### Related Clause:")
                            st.write(f"**{qa_data['clause_type']}** (Page {qa_data['page']}):")
                            st.write(f"*{qa_data['clause_text'][:200]}{'...' if len(qa_data['clause_text']) > 200 else ''}*")
                            
                    except Exception as e:
                        st.error(f"Error getting answer: {e}")
            
            st.markdown("---")
            mode_label = st.radio(
                "Viewer mode",
                ["Paged (buttons)", "Scroll (continuous)"],
                index=0,
                horizontal=True,
            )
            view_mode = "scroll" if mode_label.startswith("Scroll") else "paged"

            st.subheader("Document")
            pdf_html = """
            <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/web/pdf_viewer.css\"/>
            <style>
              .textLayer { position: absolute; left: 0; top: 0; right: 0; bottom: 0; overflow: hidden; opacity: 0.2; line-height: 1.0; }
              .textLayer > span { color: transparent; position: absolute; white-space: pre; cursor: text; transform-origin: 0% 0%; }
              .textLayer ::selection { background: rgb(0, 100, 255); }
              .highlightOverlay { position: absolute; background: rgba(255, 230, 0, 0.35); pointer-events: none; }
              #floatingHighlightBtn { position: fixed; display: none; padding: 6px 12px; background: #ffeb3b; border: 1px solid #fbc02d; border-radius: 4px; cursor: pointer; z-index: 9999; font-size: 13px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
            </style>
            <div id=\"pdf-container\" style=\"border:1px solid #ddd; padding:8px;\">
              <div id=\"pager-controls\" style=\"display:flex; gap:8px; align-items:center; margin-bottom:8px;\">
                <button id=\"prev\">Prev</button>
                <button id=\"next\">Next</button>
                <span>Page: <span id=\"page_num\">1</span> / <span id=\"page_count\">?</span></span>
                <button id=\"zoom_out\">-</button>
                <span>Zoom</span>
                <button id=\"zoom_in\">+</button>
                <button id=\"sel_highlight\">Highlight selection</button>
              </div>
              <div id=\"page-layer\" style=\"position:relative; display:inline-block;\">
                <canvas id=\"the-canvas\" style=\"display:block;\"></canvas>
                <div id=\"text-layer\" class=\"textLayer\" style=\"position:absolute; left:0; top:0;\"></div>
                <div id=\"highlight-layer\" style=\"position:absolute; left:0; top:0; pointer-events:none;\"></div>
              </div>
              <div id=\"scroll-container\" style=\"display:none; height:80vh; overflow:auto; border:1px solid #eee; padding:8px; box-sizing:border-box;\"></div>
            </div>
            <button id=\"floatingHighlightBtn\">Highlight</button>
            <script src=\"https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js\"></script>
            <script>
              (async () => {
                const VIEW_MODE = \"{view_mode}\";
                pdfjsLib.GlobalWorkerOptions.workerSrc = \"https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js\";

                const pdfUrl = \"{API_BASE}/pdf/{job_id}\";
                const resp = await fetch(pdfUrl, { credentials: 'omit' });
                if (!resp.ok) {
                  document.getElementById('pdf-container').innerHTML = "Failed to load PDF (status " + resp.status + ")";
                  return;
                }
                const buf = await resp.arrayBuffer();
                const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
                const jobId = \"{job_id}\";

                const canvas = document.getElementById('the-canvas');
                const ctx = canvas.getContext('2d');
                const pageNumSpan = document.getElementById('page_num');
                const pageCountSpan = document.getElementById('page_count');
                const prevBtn = document.getElementById('prev');
                const nextBtn = document.getElementById('next');
                const zoomInBtn = document.getElementById('zoom_in');
                const zoomOutBtn = document.getElementById('zoom_out');
                const pagerControls = document.getElementById('pager-controls');
                const scrollContainer = document.getElementById('scroll-container');
                const pageLayer = document.getElementById('page-layer');
                const textLayerDiv = document.getElementById('text-layer');
                const highlightLayerDiv = document.getElementById('highlight-layer');
                const selHighlightBtn = document.getElementById('sel_highlight');
                const floatingBtn = document.getElementById('floatingHighlightBtn');

                let currentPage = 1;
                let scale = 1.2;
                pageCountSpan.textContent = pdf.numPages;
                let currentViewport = null;

                function setCanvasSizeForViewport(canvasEl, viewport) {
                  const outputScale = window.devicePixelRatio || 1;
                  canvasEl.style.width = viewport.width + "px";
                  canvasEl.style.height = viewport.height + "px";
                  canvasEl.width = Math.floor(viewport.width * outputScale);
                  canvasEl.height = Math.floor(viewport.height * outputScale);
                  return outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;
                }

                async function highlightSelectedText(pageNum, viewport, layerDiv) {
                  const sel = window.getSelection();
                  if (!sel.rangeCount) return;
                  const selectedText = sel.toString().trim();
                  if (!selectedText) return;

                  const range = sel.getRangeAt(0);
                  const rects = range.getClientRects();
                  const containerRect = layerDiv.getBoundingClientRect();
                  
                  for (let i = 0; i < rects.length; i++) {
                    const rect = rects[i];
                    const highlightDiv = document.createElement('div');
                    highlightDiv.className = 'highlightOverlay';
                    highlightDiv.style.left = (rect.left - containerRect.left) + 'px';
                    highlightDiv.style.top = (rect.top - containerRect.top) + 'px';
                    highlightDiv.style.width = rect.width + 'px';
                    highlightDiv.style.height = rect.height + 'px';
                    layerDiv.appendChild(highlightDiv);
                  }
                  
                  sel.removeAllRanges();
                }

                async function renderPagePaged(num) {
                  const page = await pdf.getPage(num);
                  const viewport = page.getViewport({ scale });
                  currentViewport = viewport;
                  
                  const transform = setCanvasSizeForViewport(canvas, viewport);
                  await page.render({ canvasContext: ctx, viewport, transform }).promise;

                  textLayerDiv.innerHTML = '';
                  highlightLayerDiv.innerHTML = '';
                  textLayerDiv.style.width = viewport.width + 'px';
                  textLayerDiv.style.height = viewport.height + 'px';
                  highlightLayerDiv.style.width = viewport.width + 'px';
                  highlightLayerDiv.style.height = viewport.height + 'px';

                  const textContent = await page.getTextContent();
                  pdfjsLib.renderTextLayer({
                    textContent: textContent,
                    container: textLayerDiv,
                    viewport: viewport,
                    textDivs: []
                  });

                  pageNumSpan.textContent = num;
                }

                if (VIEW_MODE === \"paged\") {
                  pagerControls.style.display = \"flex\";
                  canvas.style.display = \"block\";
                  pageLayer.style.display = \"inline-block\";
                  scrollContainer.style.display = \"none\";

                  prevBtn.onclick = () => {
                    if (currentPage <= 1) return;
                    currentPage--;
                    renderPagePaged(currentPage);
                  };

                  nextBtn.onclick = () => {
                    if (currentPage >= pdf.numPages) return;
                    currentPage++;
                    renderPagePaged(currentPage);
                  };

                  zoomInBtn.onclick = () => {
                    scale = Math.min(scale + 0.2, 3.0);
                    renderPagePaged(currentPage);
                  };
                  
                  zoomOutBtn.onclick = () => {
                    scale = Math.max(scale - 0.2, 0.4);
                    renderPagePaged(currentPage);
                  };

                  selHighlightBtn.onclick = () => {
                    highlightSelectedText(currentPage, currentViewport, highlightLayerDiv);
                  };

                  renderPagePaged(currentPage);
                } else {
                  pagerControls.style.display = \"none\";
                  canvas.style.display = \"none\";
                  pageLayer.style.display = \"none\";
                  scrollContainer.style.display = \"block\";

                  const containerWidth = scrollContainer.clientWidth - 16;
                  const firstPage = await pdf.getPage(1);
                  const v1 = firstPage.getViewport({ scale: 1 });
                  const fitScale = containerWidth > 0 ? (containerWidth / v1.width) : 1.2;

                  const pageData = [];

                  for (let p = 1; p <= pdf.numPages; p++) {
                    const wrapper = document.createElement('div');
                    wrapper.style.position = 'relative';
                    wrapper.style.display = 'inline-block';
                    wrapper.style.margin = '0 0 12px 0';

                    const pageCanvas = document.createElement('canvas');
                    pageCanvas.style.display = 'block';

                    const textLayer = document.createElement('div');
                    textLayer.className = 'textLayer';
                    textLayer.style.position = 'absolute';
                    textLayer.style.left = '0';
                    textLayer.style.top = '0';

                    const highlightLayer = document.createElement('div');
                    highlightLayer.style.position = 'absolute';
                    highlightLayer.style.left = '0';
                    highlightLayer.style.top = '0';
                    highlightLayer.style.pointerEvents = 'none';

                    wrapper.appendChild(pageCanvas);
                    wrapper.appendChild(textLayer);
                    wrapper.appendChild(highlightLayer);
                    scrollContainer.appendChild(wrapper);

                    const page = await pdf.getPage(p);
                    const viewport = page.getViewport({ scale: fitScale });
                    
                    const outputScale = window.devicePixelRatio || 1;
                    pageCanvas.style.width = viewport.width + \"px\";
                    pageCanvas.style.height = viewport.height + \"px\";
                    pageCanvas.width = Math.floor(viewport.width * outputScale);
                    pageCanvas.height = Math.floor(viewport.height * outputScale);
                    const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

                    const ctxEl = pageCanvas.getContext('2d');
                    await page.render({ canvasContext: ctxEl, viewport, transform }).promise);

                    textLayer.style.width = viewport.width + 'px';
                    textLayer.style.height = viewport.height + 'px';
                    highlightLayer.style.width = viewport.width + 'px';
                    highlightLayer.style.height = viewport.height + 'px';

                    const textContent = await page.getTextContent();
                    pdfjsLib.renderTextLayer({
                      textContent: textContent,
                      container: textLayer,
                      viewport: viewport,
                      textDivs: []
                    });

                    pageData.push({ pageNum: p, viewport, highlightLayer });
                  }

                  document.addEventListener('selectionchange', () => {
                    const sel = window.getSelection();
                    if (sel && sel.toString().trim().length > 0) {
                      const range = sel.getRangeAt(0);
                      const rect = range.getBoundingClientRect();
                      floatingBtn.style.display = 'block';
                      floatingBtn.style.left = (rect.left + window.scrollX) + 'px';
                      floatingBtn.style.top = (rect.bottom + window.scrollY + 5) + 'px';
                    } else {
                      floatingBtn.style.display = 'none';
                    }
                  });

                  floatingBtn.onclick = async () => {
                    const sel = window.getSelection();
                    if (!sel.rangeCount) return;
                    const selectedText = sel.toString().trim();
                    if (!selectedText) return;

                    const range = sel.getRangeAt(0);
                    let targetPageNum = 1;
                    let targetLayer = null;

                    for (const pd of pageData) {
                      const wrapper = pd.highlightLayer.parentElement;
                      if (wrapper.contains(range.commonAncestorContainer) || range.intersectsNode(wrapper)) {
                        targetPageNum = pd.pageNum;
                        targetLayer = pd.highlightLayer;
                        break;
                      }
                    }

                    if (targetLayer) {
                      const rects = range.getClientRects();
                      const containerRect = targetLayer.getBoundingClientRect();
                      
                      for (let i = 0; i < rects.length; i++) {
                        const rect = rects[i];
                        const highlightDiv = document.createElement('div');
                        highlightDiv.className = 'highlightOverlay';
                        highlightDiv.style.left = (rect.left - containerRect.left) + 'px';
                        highlightDiv.style.top = (rect.top - containerRect.top) + 'px';
                        highlightDiv.style.width = rect.width + 'px';
                        highlightDiv.style.height = rect.height + 'px';
                        targetLayer.appendChild(highlightDiv);
                      }
                    }

                    sel.removeAllRanges();
                    floatingBtn.style.display = 'none';
                  };
                }
              })();
            </script>
            """
            pdf_html = pdf_html.replace("{view_mode}", view_mode)
            pdf_html = pdf_html.replace("{API_BASE}", API_BASE)
            pdf_html = pdf_html.replace("{job_id}", job_id)
            st.components.v1.html(pdf_html, height=700)

            
            st.subheader("📋 Detected Clauses")
            
            if clauses:
                
                clause_groups = {}
                for clause in clauses:
                    clause_type = clause.get('type', 'Unknown')
                    if clause_type not in clause_groups:
                        clause_groups[clause_type] = []
                    clause_groups[clause_type].append(clause)
                
                for clause_type, type_clauses in clause_groups.items():
                    with st.expander(f"{clause_type} ({len(type_clauses)} found)", expanded=True):
                        for i, clause in enumerate(type_clauses):
                            score = clause.get('score', 0)
                            text = clause.get('text', '')
                            page = clause.get('page', 1)
                          
                            confidence_color = "🟢" if score > 0.1 else "🟡" if score > 0.05 else "🔴"
                            confidence_text = "High" if score > 0.1 else "Medium" if score > 0.05 else "Low"
                         
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.markdown(f"**{confidence_color} {confidence_text} Confidence**")
                                st.markdown(f"**Page {page}**")
                                st.markdown(f"*{text[:200]}{'...' if len(text) > 200 else ''}*")
                            
                            with col2:
                                
                                st.progress(score)
                                st.caption(f"{score:.1%}")
                                
                                unique_key = f"goto_{clause_type}_{i}_{page}_{id(clause)}"
                                if st.button(f"Go to Page {page}", key=unique_key):
                                    st.info(f"Jumping to page {page} in PDF viewer...")
            
            else:
                st.info("No clauses detected in this document.")
            break

        time.sleep(0.05)
    else:
        st.warning(f"Timeout waiting for completion (last status={last_status}).")

else:
    st.info("Upload a PDF from the sidebar to start analysis.")