from pydantic import BaseModel

class UploadResult(BaseModel):
    message : str
    pages : str

class ExplainRequest(BaseModel):
    question : str

class ExplainResult(BaseModel):
    answer : str
    citations: list[str]

