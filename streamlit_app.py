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
                # Display PDF using base64 encoding
                try:
                    with open(tmp_path, "rb") as f:
                        pdf_bytes = f.read()
                        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
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
