import os
import time
import json
import streamlit as st
import base64
import fitz  # PyMuPDF
import re
from pathlib import Path
from string import Template

st.set_page_config(page_title="CLAWS", layout="wide")
st.title("CLAWS - Clause Law Assessment Workflow System")

# Import modules
try:
    from app.parser import parse_pdf
    from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
    from app.llm_generator import get_llm_generator
    from app.example_database import get_example_pdfs, get_example_pdf_path, get_example_pdf_info
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

st.sidebar.header("📄 Upload PDF")
uploaded = st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])

# Example PDFs Section
st.sidebar.header("📋 Example Contracts")
st.sidebar.write("Try these sample contracts:")

example_pdfs = get_example_pdfs()
for name, info in example_pdfs.items():
    with st.sidebar.expander(f"📄 {name}"):
        st.write(f"**Description:** {info['description']}")
        st.write(f"**Pages:** {info['pages']}")
        st.write(f"**Complexity:** {info['complexity']}")
        st.write(f"**Key Topics:** {', '.join(info['key_topics'])}")
        st.write(f"**Clause Types:** {', '.join(info['clause_types'])}")
        
        if st.button(f"Load {name}", key=f"load_{name}"):
            # Load the example PDF
            example_path = get_example_pdf_path(info['filename'])
            if os.path.exists(example_path):
                with open(example_path, "rb") as f:
                    uploaded = type('obj', (object,), {
                        'name': info['filename'],
                        'getvalue': lambda: f.read()
                    })()
                st.success(f"✅ Loaded {name}!")
                st.rerun()
            else:
                st.error(f"Example PDF not found: {example_path}")

if uploaded is not None:
    st.success(f"📄 Uploaded: {uploaded.name}")
    
    with st.spinner("Analyzing PDF..."):
        try:
            # Save uploaded file temporarily
            temp_path = f"temp_{uploaded.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded.getvalue())
            
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
                highlighted_pdf_data = uploaded.getvalue()
            
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
            file_name=uploaded.name.replace('.pdf', '_highlighted.pdf'),
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
        
        # Show a preview of detected clauses
        if clauses:
            st.markdown("**Detected Clauses Preview:**")
            clause_types = list(set([clause.get('type', 'Unknown') for clause in clauses]))
            st.write(f"Found {len(clause_types)} different clause types: {', '.join(clause_types[:5])}{'...' if len(clause_types) > 5 else ''}")
        
    except Exception as e:
        st.error(f"Could not display PDF: {e}")
        st.info("You can download the PDF using the button above to view it locally.")

    # Q&A Section (Second)
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
                    context_parts.insert(0, f"Document: {uploaded.name}")
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
    # Main page when no PDF is uploaded
    st.markdown("## 🚀 Welcome to CLAWS!")
    st.markdown("**Intelligent Legal Contract Analysis with AI-Powered Clause Detection**")
    
    st.markdown("### 📋 Try These Example Contracts")
    st.markdown("Click on any example below to load it instantly, or upload your own PDF from the sidebar.")
    
    # Display example PDFs in a grid
    example_pdfs = get_example_pdfs()
    cols = st.columns(2)
    
    for i, (name, info) in enumerate(example_pdfs.items()):
        with cols[i % 2]:
            with st.container():
                st.markdown(f"#### 📄 {name}")
                st.markdown(f"**{info['description']}**")
                st.markdown(f"📊 **Pages:** {info['pages']} | **Complexity:** {info['complexity']}")
                st.markdown(f"🏷️ **Topics:** {', '.join(info['key_topics'])}")
                st.markdown(f"⚖️ **Clauses:** {', '.join(info['clause_types'])}")
                
                if st.button(f"Load {name}", key=f"main_load_{name}", type="primary"):
                    example_path = get_example_pdf_path(info['filename'])
                    if os.path.exists(example_path):
                        with open(example_path, "rb") as f:
                            uploaded = type('obj', (object,), {
                                'name': info['filename'],
                                'getvalue': lambda: f.read()
                            })()
                        st.success(f"✅ Loaded {name}!")
                        st.rerun()
                    else:
                        st.error(f"Example PDF not found: {example_path}")
    
    st.markdown("---")
    st.markdown("### 🎯 What CLAWS Can Do")
    st.markdown("""
    - **🔍 Detect 16 Legal Clause Types** automatically
    - **⚖️ Assess Risk** for 6 critical clause categories  
    - **🤖 Answer Questions** about contract terms using AI
    - **📄 Highlight PDFs** with detected clauses
    - **📊 Provide Analysis** with confidence scores
    """)
    
    st.markdown("### 💡 Try Asking Questions Like:")
    st.markdown("""
    - "What is this contract about?"
    - "What are the payment terms?"
    - "What are the risks with the termination clause?"
    - "Who are the parties involved?"
    - "How can this contract be terminated?"
    """)

# Clean up temp files at the end
if 'temp_files' in locals():
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass  # Ignore cleanup errors
