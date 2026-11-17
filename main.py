
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PYORPS Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://https://queue-atlas-research-preview.mbbegun.workers.dev"
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "PYORPS backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}
