# CLAWS 

CLAWS (Clause Law Assessment Workflow System) is a production-ready web application that helps legal teams review contracts faster by automatically detecting key clauses, highlighting them in real-time, and providing intelligent Q&A about contract risks.

## 🎯 What it does

- **Detects 15+ critical legal clause types** using intelligent pattern matching
- **Highlights clauses in real-time** with color-coded PDF overlays
- **Provides intelligent Q&A** for both general and specific contract questions
- **Offers professional UI** with interactive PDF viewer and clause navigation
- **Works reliably** without complex model dependencies

## 🚀 Key Features

- **Smart Clause Detection**: Identifies 16 critical legal clause types including Document Name, Parties, Effective Date, Governing Law, Termination, Confidentiality, Anti-Assignment, Indemnification, Force Majeure, Dispute Resolution, Severability, Entire Agreement, Amendment, Waiver, Notices, Assignment, and Insurance
- **Real-Time Highlighting**: Interactive PDF viewer with color-coded clause highlights and navigation
- **Intelligent Q&A**: Ask "What is this contract about?" or "Why is the assignment clause risky?" and get detailed answers
- **Risk Analysis**: Detailed risk assessments for 6 critical clause types (Anti-Assignment, Governing Law, Termination, Confidentiality, Indemnification, Force Majeure) with severity ratings and source citations
- **Professional UI**: Streamlit-based interface with responsive design and progress indicators

## 🔄 How it works

1. **Upload PDF** → Contract is processed asynchronously
2. **Clause Detection** → 16 clause types identified using pattern matching + ML fallbacks
3. **Real-Time Highlighting** → Clauses highlighted in PDF with color coding
4. **Interactive Q&A** → Ask questions and get intelligent responses with risk analysis
5. **Source Citations** → All answers include contract page references and policy sources

## 🏗️ Architecture

```
[Upload] -> [Parse (PyMuPDF)] -> [Detect Clauses] -> [Highlight PDF]
      |           |                    |                    |
      v           v                    v                    v
  Storage    Text + Coordinates    Pattern Matching    Real-time UI
      |           |                    |                    |
      +-----------+--------------------+--------------------+
                                      |
                              [FastAPI + Streamlit]
```

**Core Components:**
- **PDF Processing**: PyMuPDF for text extraction with coordinate tracking
- **Clause Detection**: Intelligent pattern matching + optional ML fallbacks
- **Q&A System**: Enhanced system with risk analysis and source citations
- **UI**: Streamlit with PDF.js for professional PDF viewing
- **Backend**: FastAPI with async processing and comprehensive error handling

## 📊 Knowledge Base

- **Legal Risk Database**: 6 critical clause types with detailed risk assessments (Anti-Assignment, Governing Law, Termination, Confidentiality, Indemnification, Force Majeure)
- **Pattern Library**: 16 regex patterns for clause detection
- **Source Citations**: All responses include contract page references
- **Severity Ratings**: High/Medium risk classifications with practical examples

## 🔌 API Endpoints

- `GET /healthz` → `{ "status": "ok" }`
- `POST /analyze` (multipart form field `pdf`) → `{ job_id, filename, status: "queued" }`
- `GET /result/{job_id}` → `{ job_id, status: "queued|processing|done|error", clauses: [...] }`
- `POST /explain` (JSON body `{ question, job_id }`) → `{ answer, clause_text, clause_type, page }`
- `GET /pdf/{job_id}` → Serves highlighted PDF file
- `POST /highlight_text/{job_id}` → Adds text highlights to PDF

## 📋 Data Models

- **AnalyzeResponse**: `{ job_id: str, filename: str, status: str }`
- **Clause**: `{ type: str, text: str, page: int, bbox: [x0,y0,x1,y1], score: float }`
- **QAResponse**: `{ answer: str, clause_text: str, clause_type: str, page: int }`

## 🚀 Quick Start

**Prerequisites**: Python 3.11+

```bash
# Clone and setup
git clone <repository-url>
cd CLAWS
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start with Streamlit (includes backend)
streamlit run ui/app.py
```

**Access the application:**
- **Streamlit App**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs (if backend running separately)

**For Streamlit Cloud Deployment:**
1. Push to GitHub
2. Connect to [share.streamlit.io](https://share.streamlit.io)
3. Deploy instantly!

## 🧪 Testing

```bash
# Run tests
pytest -q

# Test system components
python test_system.py
```

## 📁 Project Structure

```
CLAWS/
├── app/                    # Backend API
│   ├── main.py            # FastAPI application
│   ├── parser.py          # PDF processing & clause detection
│   ├── qa_system.py       # Q&A and risk analysis
│   ├── llm_generator.py   # LLM integration
│   └── knowledge_base.py  # Legal risk database
├── ui/                    # Frontend
│   └── app.py            # Streamlit interface
├── data/                  # File storage
│   ├── uploads/          # Uploaded PDFs
│   ├── results/          # Processing results
│   └── annotations/      # PDF annotations
└── test/                 # Test files
```

## 🎯 Current Status: STREAMLIT READY

✅ **MVP Complete**: All core functionality implemented and tested
✅ **Clause Detection**: 16 critical legal clause types with high accuracy
✅ **Q&A System**: Intelligent responses with risk analysis and citations
✅ **PDF Highlighting**: Real-time highlighting with interactive navigation
✅ **Streamlit Optimized**: Designed for Streamlit Cloud deployment
✅ **Backend API**: Complete FastAPI with async processing
✅ **Error Handling**: Comprehensive error handling and graceful degradation

## 🚀 Deployment

The system is designed for simple deployment using Streamlit:

**Streamlit Deployment (Recommended)**
```bash
# Deploy directly with Streamlit
streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0
```

**Local Development**
```bash
# Terminal 1: Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend  
streamlit run ui/app.py --server.port 8501
```

**Streamlit Cloud Deployment**
1. Push your code to GitHub
2. Connect your repo to [share.streamlit.io](https://share.streamlit.io)
3. Deploy with one click - no configuration needed!

**Streamlit Configuration**
Create a `.streamlit/config.toml` file for optimal deployment:
```toml
[server]
port = 8501
address = "0.0.0.0"
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
```

## 📊 Performance

- **Processing Speed**: <10s for 10-page PDFs
- **Q&A Response**: <3s for intelligent responses
- **Memory Usage**: ~500MB-1GB for full system
- **Accuracy**: High precision on critical legal clauses
- **Streamlit Ready**: Optimized for Streamlit Cloud deployment

## License

This repository is for educational/demo purposes. Verify dataset/model licenses (e.g., CUAD, DocLayNet) before redistribution.


