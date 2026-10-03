"""POST /api/chat: a visitor asks a question and gets a cited answer, or "I don't know"."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.providers.base import ProviderError
from app.rag.answer import FALLBACK_MESSAGE, HISTORY_MESSAGES, AnswerResult, answer_question
from app.rag.guardrails import QuestionError, clean_question, mask_personal_data
from app.rag.retrieval import RetrievalResult
from app.security import client_ip, hash_ip

logger = logging.getLogger("app.chat")
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=64)
    # The real limit (500 characters) is applied by clean_question so the error is friendly.
    message: str = Field(max_length=5000)


class CitationOut(BaseModel):
    article_id: int
    title: str
    url: str
    chunk_id: int
    quote: str


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: list[CitationOut]
    abstained: bool
    handoff_offered: bool


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    state = request.app.state
    settings = state.settings

    # Rate limit per visitor. Only a salted hash of the address is used as the key.
    visitor = hash_ip(client_ip(request, settings.trust_proxy_headers), state.ip_salt)
    if not state.rate_limiter.allow(visitor):
        raise HTTPException(
            status_code=429,
            detail="You are sending messages too quickly. Please wait a few minutes and try again.",
            headers={"Retry-After": str(state.rate_limiter.retry_after(visitor))},
        )

    try:
        question = clean_question(body.message)
    except QuestionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    # Personal data is masked before the message is saved AND before it reaches the AI provider.
    question = mask_personal_data(question)

    repo = state.repository
    conversation = repo.get_conversation(body.conversation_id) if body.conversation_id else None
    if conversation is None:  # a new chat, or an old id that no longer exists
        conversation = repo.create_conversation()
    history = repo.list_messages(conversation.id, limit=HISTORY_MESSAGES)

    started = time.perf_counter()
    try:
        result = answer_question(
            question,
            history,
            repo,
            state.embedder,
            state.llm,
            min_similarity=settings.min_similarity,
            max_output_tokens=settings.max_output_tokens,
        )
    except ProviderError as error:
        # The AI provider is down, slow or not set up. The visitor still gets a safe reply and
        # the offer of a human. The message of a ProviderError never contains a secret.
        logger.warning("AI provider problem: %s", error)
        result = AnswerResult(
            answer=FALLBACK_MESSAGE,
            abstained=True,
            reason="provider_error",
            retrieval=RetrievalResult(question, settings.min_similarity, []),
        )
    latency_ms = int((time.perf_counter() - started) * 1000)

    repo.add_message(conversation.id, "user", question)
    reply = repo.add_message(
        conversation.id,
        "assistant",
        result.answer,
        citations=[citation.as_dict() for citation in result.citations],
        abstained=result.abstained,
        retrieved_chunk_ids=result.retrieved_chunk_ids,
        latency_ms=latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        model=result.model,
    )
    logger.info(
        "answer: reason=%s abstained=%s latency_ms=%s input_tokens=%s output_tokens=%s "
        "model=%s retrieved=%s",
        result.reason,
        result.abstained,
        latency_ms,
        result.input_tokens,
        result.output_tokens,
        result.model,
        result.retrieved_chunk_ids,
    )
    return ChatResponse(
        conversation_id=conversation.id,
        message_id=reply.id,
        answer=result.answer,
        citations=[CitationOut(**citation.as_dict()) for citation in result.citations],
        abstained=result.abstained,
        handoff_offered=result.abstained,
    )
