from fastapi import APIRouter, UploadFile, HTTPException, status
from app.models.schemas import UploadResult, ExplainRequest, ExplainResult

router = APIRouter()

max_bytes = 1024 * 1024 * 20
