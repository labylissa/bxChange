from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, connectors, executions, logs
from app.core.config import settings

app = FastAPI(
    title="bxChange API",
    description="Legacy Connector Platform — REST/JSON bridge for SOAP/XML systems",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(connectors.router, prefix="/api/v1")
app.include_router(executions.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}
