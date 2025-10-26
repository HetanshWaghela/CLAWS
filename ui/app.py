import os 
import time
import json
import streamlit as st
import base64
from string import Template
from uuid import uuid4
from pathlib import Path
import queue
from threading import Thread
import fitz
import tempfile
import shutil

# Import our modules
from app.parser import parse_pdf
from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
from app.llm_generator import get_llm_generator

# Data models
class AnalyzeResponse:
    def __init__(self, job_id: str, filename: str, status: str):
        self.job_id = job_id
        self.filename = filename
        self.status = status

class Clause:
    def __init__(self, type: str, text: str, page: int, bbox: list[float], score: float):
        self.type = type
        self.text = text
        self.page = page
        self.bbox = bbox
        self.score = score

class Result:
    def __init__(self, job_id: str, status: str, clauses: list[Clause] = None):
        self.job_id = job_id
        self.status = status
        self.clauses = clauses or []

class QAResponse:
    def __init__(self, answer: str, clause_text: str = "", clause_type: str = "", page: int = 0):
        self.answer = answer
        self.clause_text = clause_text
        self.clause_type = clause_type
        self.page = page

# Helper functions
def get_data_dir():
    """Get data directory, using temp directory for Streamlit Cloud"""
    if os.environ.get("STREAMLIT_CLOUD"):
        return Path(tempfile.gettempdir()) / "claws_data"
    return Path(os.environ.get("DATA_DIR", "data"))

def ensure_data_dirs():
    """Ensure all necessary directories exist"""
    data_dir = get_data_dir()
    (data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (data_dir / "results").mkdir(parents=True, exist_ok=True)
    (data_dir / "annotations").mkdir(parents=True, exist_ok=True)
    return data_dir

def write_result(result: Result):
    """Write result to file"""
    data_dir = ensure_data_dirs()
    results_dir = data_dir / "results"
    result_dict = {
        "job_id": result.job_id,
        "status": result.status,
        "clauses": [{"type": c.type, "text": c.text, "page": c.page, "bbox": c.bbox, "score": c.score} for c in result.clauses]
    }
    (results_dir / f"{result.job_id}.json").write_text(json.dumps(result_dict))

def read_result(job_id: str):
    """Read result from file"""
    data_dir = get_data_dir()
    path = data_dir / "results" / f"{job_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text() or "{}")

def cleanup_old_files():
    """Clean up files older than 1 hour"""
    try:
        data_dir = get_data_dir()
        current_time = time.time()
        for subdir in ["uploads", "results", "annotations"]:
            dir_path = data_dir / subdir
            if dir_path.exists():
                for file_path in dir_path.iterdir():
                    if file_path.is_file() and current_time - file_path.stat().st_mtime > 3600:  # 1 hour
                        file_path.unlink()
    except Exception as e:
        print(f"Cleanup error: {e}")

def process_qa_question(question: str, job_id: str, detected_clauses: list):
    """Process Q&A question directly"""
    try:
        clause_type = parse_question(question)
        
        if clause_type == 'GENERAL_CONTRACT':
            answer = generate_contract_summary(detected_clauses, question)
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
                prompt = f"{context}\n\nQuestion: {question}\n\nAnswer:"
                answer = llm_generator.generate_explanation(prompt, question)
                
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
                    llm_answer = llm_generator.generate_explanation(clause_text, question)
                    if llm_answer != "No explanation available":
                        answer = f"LLM Analysis: {llm_answer}"
                    else:
                        answer = f"No risk information available for {clause_type} clauses."
                else:
                    answer = f"No {clause_type} clause found in the contract."
            else:
                clause_text = clause['text'] if clause else ""
                answer = generate_answer(clause_text, policy, question)
            
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

def get_pdf_url(job_id: str):
    """Get PDF URL for the viewer"""
    data_dir = get_data_dir()
    highlighted_pdf_path = data_dir / "uploads" / f"{job_id}_highlighted.pdf"
    original_pdf_path = data_dir / "uploads" / f"{job_id}.pdf"
    
    if highlighted_pdf_path.exists():
        return f"/api/pdf/{job_id}"
    elif original_pdf_path.exists():
        return f"/api/pdf/{job_id}"
    else:
        return None

# Initialize session state
if 'job_queue' not in st.session_state:
    st.session_state.job_queue = queue.Queue()
if 'worker_started' not in st.session_state:
    st.session_state.worker_started = False

def worker():
    """Background worker for processing PDFs"""
    while True:
        try:
            job_id, pdf_path = st.session_state.job_queue.get()
            write_result(Result(job_id=job_id, status="processing", clauses=[]))
            clauses = parse_pdf(str(pdf_path))
            clause_objects = [Clause(type=c['type'], text=c['text'], page=c['page'], bbox=c['bbox'], score=c['score']) for c in clauses]
            write_result(Result(job_id=job_id, status="done", clauses=clause_objects))
        except Exception as e:
            write_result(Result(job_id=job_id, status="error", clauses=[]))
            print(f"Error processing job {job_id}: {e}")
        finally:
            st.session_state.job_queue.task_done()
            time.sleep(0.01)

# Start worker thread
if not st.session_state.worker_started:
    t = Thread(target=worker, daemon=True)
    t.start()
    st.session_state.worker_started = True

st.set_page_config(page_title="CLAWS", layout="wide")
st.title("CLAWS - Clause Law Assessment Workflow System")

st.sidebar.header("Upload PDF")
uploaded= st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])

if uploaded is not None:
    # Clean up old files
    cleanup_old_files()
    
    with st.spinner("Uploading and processing PDF..."):
        try:
            # Generate job ID
            job_id = str(uuid4())
            
            # Save uploaded file
            data_dir = ensure_data_dirs()
            pdf_path = data_dir / "uploads" / f"{job_id}.pdf"
            pdf_path.write_bytes(uploaded.getvalue())
            
            # Queue for processing
            write_result(Result(job_id=job_id, status="queued", clauses=[]))
            st.session_state.job_queue.put((job_id, pdf_path))
            
            st.success(f"Uploaded and queued job {job_id} (queued)")
            
        except Exception as e:
            st.error(f"Failed to upload: {e}")
            st.stop()

    placeholder= st.empty()
    last_status= "queued"
    for _ in range(200):
        try:
            body = read_result(job_id)
            if not body:
                placeholder.warning("Unknown job_id. Retrying...")
                time.sleep(0.2)
                continue
        except Exception as e:
            placeholder.error(f"Polling failed: {e}")
            time.sleep(0.2)
            continue

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
                        # Process Q&A directly
                        qa_response = process_qa_question(question, job_id, clauses)
                        
                        st.markdown("### Answer:")
                        st.write(qa_response.answer)
                        
                        if qa_response.clause_text:
                            st.markdown("### Related Clause:")
                            st.write(f"**{qa_response.clause_type}** (Page {qa_response.page}):")
                            st.write(f"*{qa_response.clause_text[:200]}{'...' if len(qa_response.clause_text) > 200 else ''}*")
                            
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

                // Get PDF data directly from Streamlit
                const pdfData = {pdf_data};
                const buf = pdfData;
                const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
                const jobId = "{job_id}";

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

                  // Highlight text directly (simplified for Streamlit)
                  try {
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
                  } catch (e) {
                    console.log('Highlight error:', e);
                  }
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
                  pagerControls.style.display = "flex";
                  canvas.style.display = "block";
                  pageLayer.style.display = "inline-block";
                  scrollContainer.style.display = "none";

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
                  pagerControls.style.display = "none";
                  canvas.style.display = "none";
                  pageLayer.style.display = "none";
                  scrollContainer.style.display = "block";

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
                    pageCanvas.style.width = viewport.width + "px";
                    pageCanvas.style.height = viewport.height + "px";
                    pageCanvas.width = Math.floor(viewport.width * outputScale);
                    pageCanvas.height = Math.floor(viewport.height * outputScale);
                    const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

                    const ctxEl = pageCanvas.getContext('2d');
                    await page.render({ canvasContext: ctxEl, viewport, transform }).promise;

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
                      try {
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
                      } catch (e) {
                        console.log('Highlight error:', e);
                      }
                    }

                    sel.removeAllRanges();
                    floatingBtn.style.display = 'none';
                  };
                }
              })();
            </script>
            """
            # Get PDF data for the viewer
            data_dir = get_data_dir()
            highlighted_pdf_path = data_dir / "uploads" / f"{job_id}_highlighted.pdf"
            original_pdf_path = data_dir / "uploads" / f"{job_id}.pdf"
            
            pdf_path = highlighted_pdf_path if highlighted_pdf_path.exists() else original_pdf_path
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode()
                
                pdf_html = pdf_html.replace("{view_mode}", view_mode)
                pdf_html = pdf_html.replace("{pdf_data}", f"base64ToArrayBuffer('{pdf_base64}')")
                pdf_html = pdf_html.replace("{job_id}", job_id)
                
                # Add base64 conversion function
                pdf_html = pdf_html.replace(
                    "// Get PDF data directly from Streamlit",
                    """// Get PDF data directly from Streamlit
                function base64ToArrayBuffer(base64) {
                    const binaryString = atob(base64);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    return bytes.buffer;
                }"""
                )
                
                st.components.v1.html(pdf_html, height=700)
            else:
                st.error("PDF file not found")

            
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

            with st.expander("Raw result JSON"):
                st.code(json.dumps(body, indent=2))
            break

        time.sleep(0.05)
    else:
        st.warning(f"Timeout waiting for completion (last status={last_status}).")

else:
    st.info("Upload a PDF from the sidebar to start analysis.")

# Simple API endpoints for Streamlit Cloud
@st.cache_data
def get_pdf_file(job_id: str):
    """Get PDF file for API endpoint"""
    data_dir = get_data_dir()
    highlighted_pdf_path = data_dir / "uploads" / f"{job_id}_highlighted.pdf"
    original_pdf_path = data_dir / "uploads" / f"{job_id}.pdf"
    
    if highlighted_pdf_path.exists():
        return str(highlighted_pdf_path)
    elif original_pdf_path.exists():
        return str(original_pdf_path)
    else:
        return None

# Health check endpoint
if st.sidebar.button("Health Check"):
    st.success("✅ System is healthy!")

# Add some debugging info in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### System Status")
st.sidebar.info(f"Data Directory: {get_data_dir()}")
st.sidebar.info(f"Queue Size: {st.session_state.job_queue.qsize()}")