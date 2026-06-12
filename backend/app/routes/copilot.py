"""Copilot chat endpoint — streams Claude's reply for the in-app assistant."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.services import copilot_service

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: Optional[dict[str, Any]] = None
    activity: Optional[list[str]] = None


@router.get("/status")
def copilot_status() -> dict[str, Any]:
    """Lets the UI show/hide the copilot input based on configuration."""
    return {"configured": copilot_service.is_configured(), "model": copilot_service.MODEL}


@router.post("/chat")
async def copilot_chat(req: ChatRequest, request: Request):
    if not copilot_service.is_configured():
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Copilot is not configured. Set ANTHROPIC_API_KEY in the backend "
                    "environment to enable the assistant."
                )
            },
        )

    messages = [m.model_dump() for m in req.messages]
    # Forward the caller's bearer token so the copilot's tools query the API with
    # the same identity (works offline too — protected routes fall back to a dev user).
    auth_token = request.headers.get("Authorization")

    async def token_stream():
        try:
            async for chunk in copilot_service.stream_reply(
                messages, req.context, req.activity, auth_token
            ):
                yield chunk
        except Exception as exc:  # surface a readable error inside the chat bubble
            yield f"\n\n[Copilot error: {exc}]"

    return StreamingResponse(
        token_stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
