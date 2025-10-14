import os 
import time
import json
import requests
import streamlit as st

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
            st.subheader("Detected blocks")
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