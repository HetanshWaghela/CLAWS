import os 
import time
import json
import requests
import streamlit as st
import base64

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="CLAWS", layout="wide")
st.title("CLAWS - Clause Law Assessment Workflow System")

st.sidebar.header("Upload PDF")
uploaded= st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])

if uploaded is not None:
    files = {"pdf": (uploaded.name, uploaded.getvalue(), "application/pdf")}
    with st.spinner("Uploading and queueing.."):
        try:
            resp= requests.post(f"{API_BASE}/analyze", files=files, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            st.error(f"Failed to upload: {e}")
            st.stop()
    data= resp.json()
    job_id= resp.json()["job_id"]
    status= data.get("status")
    st.success(f"Uploaded and queued job {job_id} ({status})")

    placeholder= st.empty()
    last_status= status
    for _ in range(200):
        try:
            r = requests.get(f"{API_BASE}/result/{job_id}", timeout=10)
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
            # Native PDF viewer via PDF.js (no iframes, no PNGs)
            st.subheader("Document")
            pdf_viewer = f"""
            <div id="pdf-container" style="border:1px solid #ddd; padding:8px;">
              <div style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                <button id=\"prev\">Prev</button>
                <button id=\"next\">Next</button>
                <span>Page: <span id=\"page_num\">1</span> / <span id=\"page_count\">?</span></span>
                <button id=\"zoom_out\">-</button>
                <span>Zoom</span>
                <button id=\"zoom_in\">+</button>
              </div>
              <canvas id=\"the-canvas\" style=\"width:100%; border:1px solid #eee;\"></canvas>
            </div>
            <script src=\"https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js\"></script>
            <script>
              (async () => {{
                pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";

                const pdfUrl = "{API_BASE}/pdf/{job_id}";
                const resp = await fetch(pdfUrl, {{ credentials: 'omit' }});
                if (!resp.ok) {{
                  document.getElementById('pdf-container').innerHTML = "Failed to load PDF (status " + resp.status + ")";
                  return;
                }}
                const buf = await resp.arrayBuffer();
                const loadingTask = pdfjsLib.getDocument({{data: buf}});
                const pdf = await loadingTask.promise;

                const canvas = document.getElementById('the-canvas');
                const ctx = canvas.getContext('2d');
                const pageNumSpan = document.getElementById('page_num');
                const pageCountSpan = document.getElementById('page_count');
                const prevBtn = document.getElementById('prev');
                const nextBtn = document.getElementById('next');
                const zoomInBtn = document.getElementById('zoom_in');
                const zoomOutBtn = document.getElementById('zoom_out');

                let currentPage = 1;
                let scale = 1.2;

                pageCountSpan.textContent = pdf.numPages;

                async function renderPage(num) {{
                  const page = await pdf.getPage(num);
                  const viewport = page.getViewport({{ scale }});
                  canvas.height = viewport.height;
                  canvas.width = viewport.width;
                  await page.render({{ canvasContext: ctx, viewport }}).promise;
                  pageNumSpan.textContent = num;
                }}

                prevBtn.onclick = () => {{
                  if (currentPage <= 1) return;
                  currentPage--;
                  renderPage(currentPage);
                }};

                nextBtn.onclick = () => {{
                  if (currentPage >= pdf.numPages) return;
                  currentPage++;
                  renderPage(currentPage);
                }};

                zoomInBtn.onclick = () => {{
                  scale = Math.min(scale + 0.2, 3.0);
                  renderPage(currentPage);
                }};
                zoomOutBtn.onclick = () => {{
                  scale = Math.max(scale - 0.2, 0.4);
                  renderPage(currentPage);
                }};

                renderPage(currentPage);
              }})();
            </script>
            """
            st.components.v1.html(pdf_viewer, height=700)

            st.write(f"Total: {len(clauses)}")
            if clauses:
                for i, c in enumerate(clauses[:10], start=1):
                    st.markdown(f"- Page {c.get('page')}: {c.get('type','Paragraph')} — score={c.get('score')}")
                    st.caption(c.get("text", "")[:300] + ("..." if len(c.get("text","")) > 300 else ""))

            with st.expander("Raw result JSON"):
                st.code(json.dumps(body, indent=2))
            break

        time.sleep(0.05)
    else:
        st.warning(f"Timeout waiting for completion (last status={last_status}).")

else:
    st.info("Upload a PDF from the sidebar to start analysis.")