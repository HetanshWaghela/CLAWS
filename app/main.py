from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="CLAWS")
app.include_router(router)

