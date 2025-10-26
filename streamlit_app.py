"""
CLAWS - Streamlit App for Community Cloud Deployment
This file starts both the FastAPI backend and Streamlit frontend.
"""

import subprocess
import sys
import os
import time
import threading
import requests
from pathlib import Path

# Start the FastAPI backend
def start_backend():
    """Start the FastAPI backend."""
    try:
        os.chdir(Path(__file__).parent)
        subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000"
        ])
        print("Backend started successfully")
    except Exception as e:
        print(f"Backend startup error: {e}")

# Start backend in background
backend_thread = threading.Thread(target=start_backend, daemon=True)
backend_thread.start()

# Wait for backend to be ready
time.sleep(5)

# Check if backend is running
try:
    response = requests.get("http://localhost:8000/healthz", timeout=5)
    if response.status_code == 200:
        print("Backend is ready!")
    else:
        print("Backend not ready, but continuing...")
except:
    print("Backend check failed, but continuing...")

# Import and run the Streamlit UI
from ui.app import *
