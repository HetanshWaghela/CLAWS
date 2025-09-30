from fastapi import APIRouter, UploadFile, HTTPException, status
from app.models.schemas import UploadResult, ExplainRequest, ExplainResult

router = APIRouter()

max_bytes = 1024 * 1024 * 20


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/upload", response_model=UploadResult)
async def upload(pdf: UploadFile) -> UploadResult:
    # data quality checks
    data = await pdf.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No data uploaded"
        )
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )
    if not data.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Not a valid PDF file",
        )
    # currently this is naive page heuristic, we will later replace it with PyMuPDF + DocLayNet path
    pages = data.count(b"/Type /Page")
    return UploadResult(message=f"received {pdf.filename}", pages=str(pages))


@router.post("/explain", response_model=ExplainResult)
def explain(req: ExplainRequest) -> ExplainResult:
    q = req.question.strip()
    if not q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question is empty"
        )
    return ExplainResult(
        answer="Stub: we will combine the clause text with the policy note and explain risk.",
        citations=["[Contract §X]", "[Policy/Guideline]"],
    )
