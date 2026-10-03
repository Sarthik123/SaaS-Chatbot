"""POST /api/handoff: a visitor asks to talk to a human.

Creates a support ticket and returns its id so the frontend can confirm the request.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/api", tags=["handoff"])

_MAX_MSG = 1000  # characters; a short note is all we need


class HandoffRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    message: str = Field(min_length=1, max_length=_MAX_MSG)


class HandoffResponse(BaseModel):
    ticket_id: int


@router.post("/handoff", response_model=HandoffResponse)
def post_handoff(body: HandoffRequest, request: Request) -> HandoffResponse:
    """Submit a human-handoff request. Returns the new ticket id."""
    repo = request.app.state.repository
    # Verify the conversation exists (if one was given); if not, still create the ticket.
    conversation_id = None
    if body.conversation_id:
        conv = repo.get_conversation(body.conversation_id)
        if conv is not None:
            conversation_id = conv.id
    ticket = repo.create_ticket(
        conversation_id=conversation_id,
        name=body.name,
        email=str(body.email),
        message=body.message,
    )
    return HandoffResponse(ticket_id=ticket.id)
