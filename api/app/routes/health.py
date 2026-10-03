"""Health check: lets the website, Render and our tests ask "is the API alive?"."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # Phase 0: only says the process is running. Phase 6 adds ?deep=1 (checks the database).
    return HealthResponse(status="ok")
