from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="CLAWS")
app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    # small, human-friendly welcome + pointers
    return {"message": "Welcome to the CLAWS API!", "docs": "/docs", "health": "/ping"}
