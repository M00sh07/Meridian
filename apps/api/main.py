from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import repositories

app = FastAPI(title="Meredian API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repositories.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

