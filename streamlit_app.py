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

# Simple test first
st.info("App is loading...")

# Try to import modules
try:
    from app.parser import parse_pdf
    from app.qa_system import parse_question, get_policy_explanation, retrieve_clause, generate_answer, generate_contract_summary
    from app.llm_generator import get_llm_generator
    st.success("✅ All modules imported successfully!")
except ImportError as e:
    st.error(f"❌ Import error: {e}")
    st.stop()

st.sidebar.header("Upload PDF")
uploaded = st.sidebar.file_uploader("Choose a contract PDF", type=["pdf"])

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
            
            # Clean up temp file
            os.remove(temp_path)
            
            st.success(f"✅ Analysis complete! Found {len(clauses)} clauses.")
            
        except Exception as e:
            st.error(f"❌ Failed to analyze PDF: {e}")
            st.stop()

    # Display results
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

    # Q&A Section
    st.subheader("❓ Ask Questions About This Contract")
    
    question = st.text_input("Ask a question about the contract:", placeholder="e.g., What are the risks with the termination clause?")
    
    if question and st.button("Get Answer"):
        with st.spinner("Analyzing question..."):
            try:
                clause_type = parse_question(question)
                
                if clause_type == 'GENERAL_CONTRACT':
                    answer = generate_contract_summary(clauses, question)
                    st.success("**Answer:**")
                    st.write(answer)
                
                elif clause_type == 'GENERAL_QUESTION':
                    if clauses:
                        context = "Contract clauses detected:\n"
                        for clause in clauses[:10]:
                            context += f"- {clause.get('type', 'Unknown')}: {clause.get('text', '')[:100]}...\n"
                        
                        try:
                            llm_generator = get_llm_generator()
                            prompt = f"{context}\n\nQuestion: {question}\n\nAnswer:"
                            answer = llm_generator.generate_explanation(prompt, question)
                        except Exception as llm_error:
                            st.warning(f"LLM not available: {llm_error}")
                            answer = "I can help you understand this contract. Try asking about specific clauses like 'What are the risks with the assignment clause?' or 'Tell me about the termination clause.'"
                        
                        if answer and answer != "No explanation available":
                            st.success("**Answer:**")
                            st.write(answer)
                        else:
                            st.info("I can help you understand this contract. Try asking about specific clauses like 'What are the risks with the assignment clause?' or 'Tell me about the termination clause.'")
                    else:
                        st.warning("No contract clauses were detected. Please ensure the contract was properly analyzed.")
                
                elif clause_type:
                    clause = retrieve_clause(clause_type, clauses)
                    policy = get_policy_explanation(clause_type)
                    
                    if not policy:
                        clause_text = clause['text'] if clause else ""
                        if clause_text:
                            try:
                                llm_generator = get_llm_generator()
                                llm_answer = llm_generator.generate_explanation(clause_text, question)
                                if llm_answer != "No explanation available":
                                    answer = f"LLM Analysis: {llm_answer}"
                                else:
                                    answer = f"No risk information available for {clause_type} clauses."
                            except Exception as llm_error:
                                answer = f"No risk information available for {clause_type} clauses. (LLM not available)"
                        else:
                            answer = f"No {clause_type} clause found in the contract."
                    else:
                        clause_text = clause['text'] if clause else ""
                        answer = generate_answer(clause_text, policy, question)
                    
                    st.success("**Answer:**")
                    st.write(answer)
                    
                    if clause:
                        st.info(f"**Found on page {clause.get('page', 1)}:** {clause.get('text', '')[:200]}...")
                
                else:
                    st.info("I can help you understand this contract. Try asking about specific clauses or general questions like 'What is this contract about?'")
                    
            except Exception as e:
                st.error(f"Error processing question: {str(e)}")

    # PDF Viewer
    st.subheader("📄 Document Viewer")
    
    # Use Streamlit's built-in PDF display
    try:
        st.download_button(
            label="📥 Download PDF",
            data=uploaded.getvalue(),
            file_name=uploaded.name,
            mime="application/pdf"
        )
        
        # Show PDF using Streamlit's PDF component
        st.markdown("**PDF Preview:**")
        st.pdf(uploaded.getvalue())
        
    except Exception as e:
        st.error(f"Could not display PDF: {e}")
        st.info("You can download the PDF from the sidebar to view it locally.")

else:
    st.info("📁 Upload a PDF from the sidebar to start analysis.")
