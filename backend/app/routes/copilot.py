"""Copilot chat endpoint — streams Claude's reply for the in-app assistant."""

from __future__ import annotations

from datetime import date as _date
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


class ActionRequest(BaseModel):
    text: str
    plan: Optional[dict[str, Any]] = None
    day: Optional[str] = None
    trucks: Optional[list[dict[str, Any]]] = None
    objective: str = "balanced"


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
                    "Optiroute is not configured. Set GROQ_API_KEY in the backend "
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


def _replan_summary(ids: list[int], diff: dict[str, Any]) -> str:
    bits = [
        f"Took Truck {', '.join(map(str, ids))} out of service and re-optimised "
        f"{diff['replanned_stops']} remaining stop(s)."
    ]
    if diff.get("reassigned_count"):
        bits.append(f"{diff['reassigned_count']} reassigned.")
    if diff.get("recovered_count"):
        bits.append(f"{diff['recovered_count']} recovered.")
    if diff.get("newly_unassigned_count"):
        bits.append(f"⚠ {diff['newly_unassigned_count']} can no longer be served.")
    if diff.get("cost_delta_tnd") is not None:
        bits.append(f"Cost Δ {diff['cost_delta_tnd']:+.0f} TND.")
    return " ".join(bits)


@router.post("/action")
def copilot_action(req: ActionRequest):
    """Agentic write-tools (W3.1): interpret a plain-language instruction and
    return a grounded PROPOSAL — a plan summary, a truck explanation, or a
    breakdown-recovery plan ready for one-click approval. Deterministic and
    LLM-free, so it works whether or not Optiroute (Groq) is configured."""
    from app.services import copilot_actions

    intent = copilot_actions.interpret(req.text)
    action = intent.get("action")
    plan = req.plan or {}

    if action == "help":
        return copilot_actions.help_text()

    if action == "summary":
        if not plan.get("trucks"):
            return {"action": "summary", "summary": "No plan loaded yet — generate a plan first.", "applies": False}
        return copilot_actions.plan_summary(plan)

    if action == "explain":
        tid = intent.get("truck_id")
        if tid is None:
            return {"action": "explain", "summary": "Which truck? e.g. “explain truck 5”.", "applies": False}
        if not plan.get("trucks"):
            return {"action": "explain", "summary": "No plan loaded yet — generate a plan first.", "applies": False}
        from app.routes.optimization import _explain_truck
        try:
            ex = _explain_truck(plan, tid)
        except Exception as exc:  # noqa: BLE001 — surface a friendly message
            return {"action": "explain", "summary": f"Couldn't explain truck {tid}: {exc}", "applies": False}
        return {
            "action": "explain",
            "title": f"Why {ex.get('truck_label') or f'Truck {tid}'}",
            "summary": ex.get("summary"),
            "explain": ex,
            "applies": False,
        }

    if action == "replan":
        ids = intent.get("truck_ids") or []
        if not ids:
            return {"action": "replan", "summary": "Which truck broke down? e.g. “truck 3 broke down”.", "applies": False}
        if not plan.get("trucks"):
            return {"action": "replan", "summary": "No plan loaded to recover from — generate a plan first.", "applies": False}
        day_str = req.day or plan.get("day")
        try:
            day = _date.fromisoformat(str(day_str))
        except (TypeError, ValueError):
            return {"action": "replan", "summary": "I need the plan's day to replan.", "applies": False}
        from app.routes.optimization import compute_replan
        try:
            res = compute_replan(plan, day, ids, [], req.objective, req.trucks)
        except ValueError as exc:
            return {"action": "replan", "summary": str(exc), "applies": False}
        except Exception as exc:  # noqa: BLE001
            return {"action": "replan", "summary": f"Re-plan failed: {exc}", "applies": False}
        return {
            "action": "replan",
            "title": f"Recovery plan — Truck {', '.join(map(str, ids))} down",
            "summary": _replan_summary(ids, res["diff"]),
            "plan": res["plan"],
            "diff": res["diff"],
            "applies": True,
        }

    return {
        "action": "unknown",
        "summary": "I can summarise the plan, explain a truck, or replan after a breakdown. Type “help”.",
        "applies": False,
        "can_chat": True,
    }
