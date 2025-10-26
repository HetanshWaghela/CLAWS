import os
import time
import json
import streamlit as st
import base64
import fitz  
import re
from pathlib import Path
from string import Template

st.set_page_config(page_title="CLAWS", layout="wide")

# Dark theme toggle at the top
dark_mode = st.toggle("🌙 Dark Mode", help="Toggle dark mode", key="dark_mode_toggle")

st.title("CLAWS - Clause Law Assessment Workflow System")

# Apply dark theme CSS
if dark_mode:
    st.markdown("""
    <style>
    /* Main app background */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Main content area */
    .main .block-container {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Sidebar styling */
    .stSidebar {
        background-color: #1e1e1e;
    }
    .stSidebar .sidebar-content {
        background-color: #1e1e1e;
    }
    
    /* All text elements */
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: #fafafa !important;
    }
    
    /* Form labels and inputs */
    .stSelectbox label, .stTextInput label, .stTextArea label, .stFileUploader label {
        color: #fafafa !important;
    }
    
    /* Buttons */
    .stButton button {
        background-color: #2d2d2d;
        color: #fafafa;
        border: 1px solid #555;
    }
    .stButton button:hover {
        background-color: #3d3d3d;
    }
    
    /* File uploader */
    .stFileUploader {
        background-color: #2d2d2d !important;
        border: 1px solid #555 !important;
    }
    .stFileUploader label {
        color: #fafafa !important;
    }
    .stFileUploader .uploadedFile {
        background-color: #2d2d2d !important;
        color: #fafafa !important;
    }
    .stFileUploader .uploadedFile .file-name {
        color: #fafafa !important;
    }
    .stFileUploader .uploadedFile .file-size {
        color: #cccccc !important;
    }
    .stFileUploader .uploadedFile .file-actions {
        color: #fafafa !important;
    }
    
    /* Drag and drop text */
    .stFileUploader .uploadedFile::before {
        color: #fafafa !important;
    }
    .stFileUploader .uploadedFile::after {
        color: #cccccc !important;
    }
    
    /* Toggle switch */
    .stToggle {
        background-color: #2d2d2d;
    }
    
    /* Success messages */
    .stSuccess {
        background-color: #1e3a1e;
        border-color: #4caf50;
        color: #fafafa;
    }
    .stSuccess .stMarkdown {
        color: #fafafa !important;
    }
    
    /* Error messages */
    .stError {
        background-color: #3a1e1e;
        border-color: #f44336;
        color: #fafafa;
    }
    .stError .stMarkdown {
        color: #fafafa !important;
    }
    
    /* Warning messages */
    .stWarning {
        background-color: #3a3a1e;
        border-color: #ff9800;
        color: #fafafa;
    }
    .stWarning .stMarkdown {
        color: #fafafa !important;
    }
    
    /* Info messages */
    .stInfo {
        background-color: #1e3a3a;
        border-color: #2196f3;
        color: #fafafa;
    }
    .stInfo .stMarkdown {
        color: #fafafa !important;
    }
    
    /* Metrics */
    .metric-container {
        background-color: #2d2d2d;
        border: 1px solid #555;
    }
    .metric-container .metric-value {
        color: #fafafa !important;
    }
    .metric-container .metric-label {
        color: #cccccc !important;
    }
    
    /* Progress bars */
    .stProgress .stProgressBar {
        background-color: #2d2d2d;
    }
    
    /* Columns */
    .stColumn {
        background-color: transparent;
    }
    
    /* General text override */
    * {
        color: #fafafa !important;
    }
    
    /* Specific overrides for better readability */
    .stMarkdown strong, .stMarkdown b {
        color: #ffffff !important;
    }
    .stMarkdown em, .stMarkdown i {
        color: #e0e0e0 !important;
    }
    </style>
    """, unsafe_allow_html=True)


try:
    from app.parser import parse_pdf
    from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
    from app.llm_generator import get_llm_generator
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

st.sidebar.header("📋 Try Example Contracts")
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("Co-Branding Agreement", use_container_width=True):
        with open("data/example_contracts/co_branding.pdf", "rb") as f:
            st.session_state.example_pdf = f.read()
            st.session_state.example_name = "Co-Branding Agreement.pdf"
with col2:
    if st.button("Affiliate Agreement", use_container_width=True):
        with open("data/example_contracts/affiliate.pdf", "rb") as f:
            st.session_state.example_pdf = f.read()
            st.session_state.example_name = "Affiliate Agreement.pdf"

st.sidebar.header("📄 Upload Your Own PDF")
uploaded = st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])


pdf_data = None
pdf_name = None

if uploaded is not None:
    pdf_data = uploaded.getvalue()
    pdf_name = uploaded.name
    st.success(f"📄 Uploaded: {pdf_name}")
elif 'example_pdf' in st.session_state:
    pdf_data = st.session_state.example_pdf
    pdf_name = st.session_state.example_name
    st.success(f"📄 Example loaded: {pdf_name}")

if pdf_data is not None:
    with st.spinner("Analyzing PDF..."):
        try:
            # Save file temporarily
            temp_path = f"temp_{pdf_name}"
            with open(temp_path, "wb") as f:
                f.write(pdf_data)
            
            # Parse PDF directly
            clauses = parse_pdf(temp_path)
            
            # Check if highlighted PDF was created
            highlighted_path = temp_path.replace('.pdf', '_highlighted.pdf')
            if os.path.exists(highlighted_path):
                # Use highlighted PDF for display
                with open(highlighted_path, "rb") as f:
                    highlighted_pdf_data = f.read()
                # Don't delete yet - keep for Q&A
            else:
                # Fallback to original
                highlighted_pdf_data = pdf_data
            
            # Store temp files for later cleanup
            temp_files = [temp_path]
            if os.path.exists(highlighted_path):
                temp_files.append(highlighted_path)
            
            st.success(f"✅ Analysis complete! Found {len(clauses)} clauses.")
            
        except Exception as e:
            st.error(f"❌ Failed to analyze PDF: {e}")
            st.stop()

    # PDF Viewer (First)
    st.subheader("📄 Document Viewer (with Highlights)")
    
    # Simple PDF display using base64
    try:
        # Use highlighted PDF data
        st.download_button(
            label="📥 Download Highlighted PDF",
            data=highlighted_pdf_data,
            file_name=pdf_name.replace('.pdf', '_highlighted.pdf'),
            mime="application/pdf"
        )
        
        # Display PDF using official streamlit-pdf component
        st.markdown("**PDF Preview (with detected clause highlights):**")
        
        # Use the official st.pdf() component
        try:
            st.pdf(highlighted_pdf_data, height=600)
        except Exception as pdf_error:
            st.warning(f"PDF viewer not available: {pdf_error}")
            st.info("📄 PDF is ready for download. Click the download button above to view the highlighted PDF with all detected clauses.")
        
        # Show PDF metadata
        st.markdown("**PDF Information:**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("File Size", f"{len(highlighted_pdf_data) / 1024:.1f} KB")
        with col2:
            st.metric("Clauses Found", f"{len(clauses)}")
        
       
        if clauses:
            st.markdown("**Detected Clauses Preview:**")
            clause_types = list(set([clause.get('type', 'Unknown') for clause in clauses]))
            st.write(f"Found {len(clause_types)} different clause types: {', '.join(clause_types[:5])}{'...' if len(clause_types) > 5 else ''}")
        
    except Exception as e:
        st.error(f"Could not display PDF: {e}")
        st.info("You can download the PDF using the button above to view it locally.")

   
    st.subheader("❓ Ask Questions About This Contract")
    
    question = st.text_input("Ask ANY question about this contract:", placeholder="e.g., What is this contract about? What are the payment terms? Who are the parties? What are the risks?")
    
    if question and st.button("Get Answer"):
        with st.spinner("Analyzing question..."):
            try:
                # Always use LLM for ANY question about the PDF
                if clauses:
                    # Create comprehensive context from all detected clauses
                    context_parts = []
                    for clause in clauses:
                        clause_type_name = clause.get('type', 'Unknown')
                        clause_text = clause.get('text', '')
                        page_num = clause.get('page', 'Unknown')
                        context_parts.append(f"[Page {page_num}] {clause_type_name}: {clause_text}")
                    
                    # Add document metadata
                    context_parts.insert(0, f"Document: {pdf_name}")
                    context_parts.insert(1, f"Total clauses detected: {len(clauses)}")
                    
                    context = " ".join(context_parts)
                    
                    try:
                        llm_generator = get_llm_generator()
                        answer = llm_generator.generate_explanation(context, question)
                        
                        if answer and answer != "No explanation available":
                            st.success("**Answer:**")
                            st.write(answer)
                        else:
                            # Fallback: Try to find relevant clauses manually
                            relevant_clauses = []
                            question_lower = question.lower()
                            
                            for clause in clauses:
                                clause_text = clause.get('text', '').lower()
                                if any(word in clause_text for word in question_lower.split() if len(word) > 3):
                                    relevant_clauses.append(clause)
                            
                            if relevant_clauses:
                                st.success("**Answer:**")
                                st.write("Based on the contract analysis, here are the relevant sections:")
                                for i, clause in enumerate(relevant_clauses[:3], 1):
                                    st.write(f"{i}. **{clause.get('type', 'Unknown')}** (Page {clause.get('page', 'Unknown')}):")
                                    st.write(f"   {clause.get('text', '')[:200]}...")
                            else:
                                st.info("I couldn't find specific information about your question in this contract. Try asking about specific topics like 'termination', 'payment', 'liability', or 'confidentiality'.")
                    except Exception as llm_error:
                        st.warning(f"AI analysis not available: {llm_error}")
                        st.info("I can help you understand this contract. Try asking about specific clauses like 'What are the risks with the assignment clause?' or 'Tell me about the termination clause.'")
                else:
                    st.warning("No contract clauses were detected. Please ensure the contract was properly analyzed.")
                    
            except Exception as e:
                st.error(f"Error processing question: {e}")

    # Display results (Third)
    if clauses:
        st.subheader("📋 Detected Clauses")
        
        # Group clauses by type
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
    else:
        st.info("No clauses detected in this document.")

else:
    st.info("📁 Upload a PDF from the sidebar to start analysis.")

# Clean up temp files at the end
if 'temp_files' in locals():
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass  # Ignore cleanup errors
