"""POST /api/feedback: a visitor gives a thumbs-up or thumbs-down on an answer."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["feedback"])


class FeedbackRequest(BaseModel):
    message_id: str = Field(max_length=64)
    rating: str  # "up" or "down"
    comment: str | None = Field(default=None, max_length=500)


class FeedbackResponse(BaseModel):
    feedback_id: int


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(body: FeedbackRequest, request: Request) -> FeedbackResponse:
    """Record a visitor's rating. Returns the new feedback id."""
    try:
        record = request.app.state.repository.add_feedback(
            body.message_id, body.rating, body.comment
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return FeedbackResponse(feedback_id=record.id)
