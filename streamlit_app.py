"""
CLAWS - Simplified Streamlit App (No Backend Required)
This version integrates all functionality directly into Streamlit.
"""

import streamlit as st
import fitz
import re
import tempfile
import os
import base64
from pathlib import Path
from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
from app.parser import parse_pdf

st.set_page_config(page_title="CLAWS", layout="wide")
st.title("CLAWS - Clause Law Assessment Workflow System")

# Sidebar for PDF upload
st.sidebar.header("Upload PDF")
uploaded_file = st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])

if uploaded_file is not None:
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    
    try:
        # Process PDF
        with st.spinner("Processing PDF..."):
            clauses = parse_pdf(tmp_path)
        
        if clauses:
            st.success(f"Found {len(clauses)} clauses!")
            
            # Create two columns for PDF viewer and clauses
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.header("PDF Viewer")
                
                # Create PDF viewer using PDF.js (same as ui/app.py)
                mode_label = st.radio(
                    "Viewer mode",
                    ["Paged (buttons)", "Scroll (continuous)"],
                    index=0,
                    horizontal=True,
                )
                view_mode = "scroll" if mode_label.startswith("Scroll") else "paged"
                
                # Convert PDF to base64 for PDF.js
                try:
                    with open(tmp_path, "rb") as f:
                        pdf_bytes = f.read()
                        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    
                    pdf_html = f"""
                    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/web/pdf_viewer.css"/>
                    <style>
                      .textLayer {{ position: absolute; left: 0; top: 0; right: 0; bottom: 0; overflow: hidden; opacity: 0.2; line-height: 1.0; }}
                      .textLayer > span {{ color: transparent; position: absolute; white-space: pre; cursor: text; transform-origin: 0% 0%; }}
                      .textLayer ::selection {{ background: rgb(0, 100, 255); }}
                      .highlightOverlay {{ position: absolute; background: rgba(255, 230, 0, 0.35); pointer-events: none; }}
                    </style>
                    <div id="pdf-container" style="border:1px solid #ddd; padding:8px;">
                      <div id="pager-controls" style="display:flex; gap:8px; align-items:center; margin-bottom:8px;">
                        <button id="prev">Prev</button>
                        <button id="next">Next</button>
                        <span>Page: <span id="page_num">1</span> / <span id="page_count">?</span></span>
                        <button id="zoom_out">-</button>
                        <span>Zoom</span>
                        <button id="zoom_in">+</button>
                      </div>
                      <div id="page-layer" style="position:relative; display:inline-block;">
                        <canvas id="the-canvas" style="display:block;"></canvas>
                        <div id="text-layer" class="textLayer" style="position:absolute; left:0; top:0;"></div>
                        <div id="highlight-layer" style="position:absolute; left:0; top:0; pointer-events:none;"></div>
                      </div>
                      <div id="scroll-container" style="display:none; height:80vh; overflow:auto; border:1px solid #eee; padding:8px; box-sizing:border-box;"></div>
                    </div>
                    <script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js"></script>
                    <script>
                      (async () => {{
                        const VIEW_MODE = "{view_mode}";
                        pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";

                        const pdfData = "data:application/pdf;base64,{base64_pdf}";
                        const pdf = await pdfjsLib.getDocument(pdfData).promise;

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

                        let currentPage = 1;
                        let scale = 1.2;
                        pageCountSpan.textContent = pdf.numPages;
                        let currentViewport = null;

                        function setCanvasSizeForViewport(canvasEl, viewport) {{
                          const outputScale = window.devicePixelRatio || 1;
                          canvasEl.style.width = viewport.width + "px";
                          canvasEl.style.height = viewport.height + "px";
                          canvasEl.width = Math.floor(viewport.width * outputScale);
                          canvasEl.height = Math.floor(viewport.height * outputScale);
                          return outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;
                        }}

                        async function renderPagePaged(num) {{
                          const page = await pdf.getPage(num);
                          const viewport = page.getViewport({{ scale }});
                          currentViewport = viewport;
                          
                          const transform = setCanvasSizeForViewport(canvas, viewport);
                          await page.render({{ canvasContext: ctx, viewport, transform }}).promise;

                          textLayerDiv.innerHTML = '';
                          highlightLayerDiv.innerHTML = '';
                          textLayerDiv.style.width = viewport.width + 'px';
                          textLayerDiv.style.height = viewport.height + 'px';
                          highlightLayerDiv.style.width = viewport.width + 'px';
                          highlightLayerDiv.style.height = viewport.height + 'px';

                          const textContent = await page.getTextContent();
                          pdfjsLib.renderTextLayer({{
                            textContent: textContent,
                            container: textLayerDiv,
                            viewport: viewport,
                            textDivs: []
                          }});

                          pageNumSpan.textContent = num;
                        }}

                        if (VIEW_MODE === "paged") {{
                          pagerControls.style.display = "flex";
                          canvas.style.display = "block";
                          pageLayer.style.display = "inline-block";
                          scrollContainer.style.display = "none";

                          prevBtn.onclick = () => {{
                            if (currentPage <= 1) return;
                            currentPage--;
                            renderPagePaged(currentPage);
                          }};

                          nextBtn.onclick = () => {{
                            if (currentPage >= pdf.numPages) return;
                            currentPage++;
                            renderPagePaged(currentPage);
                          }};

                          zoomInBtn.onclick = () => {{
                            scale = Math.min(scale + 0.2, 3.0);
                            renderPagePaged(currentPage);
                          }};
                          
                          zoomOutBtn.onclick = () => {{
                            scale = Math.max(scale - 0.2, 0.4);
                            renderPagePaged(currentPage);
                          }};

                          renderPagePaged(currentPage);
                        }} else {{
                          pagerControls.style.display = "none";
                          canvas.style.display = "none";
                          pageLayer.style.display = "none";
                          scrollContainer.style.display = "block";

                          const containerWidth = scrollContainer.clientWidth - 16;
                          const firstPage = await pdf.getPage(1);
                          const v1 = firstPage.getViewport({{ scale: 1 }});
                          const fitScale = containerWidth > 0 ? (containerWidth / v1.width) : 1.2;

                          for (let p = 1; p <= pdf.numPages; p++) {{
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
                            const viewport = page.getViewport({{ scale: fitScale }});
                            
                            const outputScale = window.devicePixelRatio || 1;
                            pageCanvas.style.width = viewport.width + "px";
                            pageCanvas.style.height = viewport.height + "px";
                            pageCanvas.width = Math.floor(viewport.width * outputScale);
                            pageCanvas.height = Math.floor(viewport.height * outputScale);
                            const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;

                            const ctxEl = pageCanvas.getContext('2d');
                            await page.render({{ canvasContext: ctxEl, viewport, transform }}).promise);

                            textLayer.style.width = viewport.width + 'px';
                            textLayer.style.height = viewport.height + 'px';
                            highlightLayer.style.width = viewport.width + 'px';
                            highlightLayer.style.height = viewport.height + 'px';

                            const textContent = await page.getTextContent();
                            pdfjsLib.renderTextLayer({{
                              textContent: textContent,
                              container: textLayer,
                              viewport: viewport,
                              textDivs: []
                            }});
                          }}
                        }}
                      }})();
                    </script>
                    """
                    
                    st.components.v1.html(pdf_html, height=700)
                    
                except Exception as e:
                    st.error(f"Error displaying PDF: {e}")
                    # Fallback: show PDF download link
                    st.download_button(
                        label="Download PDF",
                        data=pdf_bytes,
                        file_name=uploaded_file.name,
                        mime="application/pdf"
                    )
            
            with col2:
                st.header("Detected Clauses")
                for i, clause in enumerate(clauses):
                    with st.expander(f"{clause['type']} (Page {clause['page']})"):
                        st.write(f"**Text:** {clause['text']}")
                        st.write(f"**Page:** {clause['page']}")
                        st.write(f"**Score:** {clause['score']}")
            
            # Q&A Section
            st.header("Ask Questions About the Contract")
            question = st.text_input("Enter your question:")
            
            if question and st.button("Get Answer"):
                with st.spinner("Generating answer..."):
                    # Parse question
                    question_type = parse_question(question)
                    
                    if question_type == 'GENERAL_CONTRACT':
                        answer = generate_contract_summary(clauses, question)
                    else:
                        # Find relevant clause
                        clause = retrieve_clause(question_type, clauses)
                        if clause:
                            policy = get_policy_explanation(question_type)
                            answer = generate_answer(clause['text'], policy, question)
                        else:
                            answer = "No relevant clause found for this question."
                    
                    st.write("**Answer:**")
                    st.write(answer)
        else:
            st.warning("No clauses detected in the PDF.")
    
    except Exception as e:
        st.error(f"Error processing PDF: {e}")
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

else:
    st.info("Please upload a PDF file to get started.")
    st.markdown("""
    ### How to use CLAWS:
    1. Upload a contract PDF using the sidebar
    2. Wait for clause detection to complete
    3. Ask questions about the contract
    4. Get intelligent answers with risk analysis
    """)
