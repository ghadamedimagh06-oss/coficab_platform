"""Claude-powered dispatch copilot (with tool access to the live platform).

Turns the static "Assistant" panel into a real LLM copilot. Two grounding paths:

1. **Screen context** — the frontend sends a compact snapshot of whatever the
   dispatcher is currently looking at (active plan, KPI cards, fleet status,
   recent actions). We inject it into the system prompt so answers about the
   current screen are instant and concrete.
2. **Tools** — for questions that go beyond the current screen ("how's the whole
   fleet", "any open incidents", "what does the dashboard KPI say"), Claude can
   call read-only tools that hit the platform's own REST API. This reuses every
   existing offline/mock fallback and the same data the UI sees, with no extra
   DB-session plumbing on the streaming path.

We run a manual agentic loop so we can stream text as it is produced while still
executing tool calls between turns. Credentials resolve from the environment the
standard way (``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN``); when neither is
set the route degrades gracefully instead of 500-ing.
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Optional

# Opus 4.8 — Anthropic's most capable model. Override per-deployment if needed.
MODEL = os.getenv("COPILOT_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.getenv("COPILOT_MAX_TOKENS", "1024"))
# Base URL the copilot's tools call back into (this same backend).
API_BASE = os.getenv("COPILOT_API_BASE", "http://127.0.0.1:8000")
# Safety cap on the agentic loop so a tool-happy turn can't run forever.
MAX_TOOL_ITERATIONS = int(os.getenv("COPILOT_MAX_TOOL_ITERATIONS", "6"))

# Cap the injected screen context so an oversized page payload can't blow the prompt.
_MAX_CONTEXT_CHARS = 20_000
# Cap each tool result so a huge transports list can't blow the context either.
_MAX_TOOL_RESULT_CHARS = 16_000

_SYSTEM_PROMPT = """\
You are the COFICAB Dispatch Copilot, an assistant embedded in COFICAB's \
logistics planning platform. COFICAB runs truck deliveries of wire/cable from a \
depot at COFICAB Sidi Hassine (Tunis, Tunisia) to client factories. The platform \
plans daily truck routes with an OR-Tools VRPTW optimizer (capacity + time \
windows), tracks deliveries, and computes operational KPIs.

Your job is to help dispatchers and planners understand and act on operations: \
explain why a route or plan looks the way it does, summarize a plan, flag risks \
(capacity overflows, late ETAs, hours-of-service warnings, split mismatches), \
compare options, and answer operational questions.

You have two sources of truth:
- The CONTEXT block below is a live snapshot of the screen the user is on. Prefer \
it for questions about what they are currently looking at.
- The tools let you look up live data across the whole platform (KPIs, fleet, \
transports/plan, incidents, live tracking, agents, dispatch logs). Call a tool \
when the answer needs data that is not in the CONTEXT block. Do not call tools \
for data already present in the context.

Rules:
- Ground every answer in the context or in tool results. Prefer concrete numbers \
over generalities. If the data needed is genuinely unavailable, say so plainly — \
do not invent trucks, clients, quantities, or times.
- Be concise and operational. Lead with the answer, then the reasoning. Use short \
bullets for lists. Quantities are in "positions"; distances in km; times in 24h \
local time.
- You are an assistant, not an autopilot: recommend actions (re-route, split a \
delivery, reassign a truck) but do not claim to have executed them.
"""

# --- Tool definitions (read-only views of the platform's own REST API) ---------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_kpis",
        "description": (
            "Get the current operational KPI cards (on-time delivery, fleet "
            "utilization, cost, distance, etc.) as shown on the dashboard. Use "
            "for questions about overall performance metrics."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_fleet",
        "description": (
            "List fleet resources. 'trucks' = vehicles with capacity/status, "
            "'drivers' = drivers with status, 'clients' = client directory, "
            "'utilization' = per-truck utilization. Use for fleet/driver/client questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["trucks", "drivers", "clients", "utilization"],
                    "description": "Which fleet resource to list.",
                }
            },
            "required": ["kind"],
        },
    },
    {
        "name": "get_transports",
        "description": (
            "List planned/active transport deliveries (the daily plan rows: "
            "client, truck, quantities, times, status). Optionally filter by day "
            "(YYYY-MM-DD). Use for questions about the plan, routes, or deliveries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {"type": "string", "description": "Day filter as YYYY-MM-DD (optional)."},
                "limit": {"type": "integer", "description": "Max rows (default 200)."},
            },
        },
    },
    {
        "name": "get_incidents",
        "description": (
            "Get logistics incidents/alerts (breakdowns, delays, SLA risks). "
            "Set stats=true for aggregate counts instead of the list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "stats": {"type": "boolean", "description": "Return aggregate stats instead of the list."}
            },
        },
    },
    {
        "name": "get_tracking_live",
        "description": "Get live tracking of in-flight transports (positions, ETAs, status).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_agent_status",
        "description": "Get the status/health of the four background automation agents (collector, optimizer, monitor, notifier).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_dispatch_logs",
        "description": "Get recent driver dispatch/notification logs (which mission briefs were sent and their status).",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Map tool name -> (HTTP path builder). Each returns a path string given the input.
_TOOL_ROUTES = {
    "get_kpis": lambda i: "/api/metrics/kpi",
    "get_fleet": lambda i: f"/api/fleet/{i.get('kind', 'trucks')}",
    "get_transports": lambda i: "/api/data/transports?" + _qs(
        {"day": i.get("day"), "limit": i.get("limit") or 200}
    ),
    "get_incidents": lambda i: "/api/incidents/stats" if i.get("stats") else "/api/incidents",
    "get_tracking_live": lambda i: "/api/tracking/live",
    "get_agent_status": lambda i: "/api/agents/status",
    "get_dispatch_logs": lambda i: "/api/dispatch/logs",
}


def _qs(params: dict[str, Any]) -> str:
    from urllib.parse import urlencode

    return urlencode({k: v for k, v in params.items() if v not in (None, "")})


_client = None


def _get_client():
    """Lazily build a shared AsyncAnthropic client (reads creds from env)."""
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic

        _client = AsyncAnthropic()
    return _client


def is_configured() -> bool:
    """True when an Anthropic credential is available in the environment."""
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _format_context(context: Optional[dict[str, Any]], activity: Optional[list[str]]) -> str:
    """Render the page snapshot + recent actions as a compact context block."""
    parts: list[str] = []
    if context:
        try:
            blob = json.dumps(context, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            blob = str(context)
        if len(blob) > _MAX_CONTEXT_CHARS:
            blob = blob[:_MAX_CONTEXT_CHARS] + " …(truncated)"
        parts.append("Current screen data (JSON):\n" + blob)
    if activity:
        recent = "\n".join(f"- {item}" for item in activity[-20:])
        parts.append("Recent actions / events:\n" + recent)
    if not parts:
        return "No screen data was provided for this turn. Use tools to look up what you need."
    return "\n\n".join(parts)


def build_system_prompt(context: Optional[dict[str, Any]], activity: Optional[list[str]]) -> str:
    return f"{_SYSTEM_PROMPT}\n\n--- CONTEXT ---\n{_format_context(context, activity)}"


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only well-formed user/assistant turns with non-empty text."""
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content})
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    return cleaned


async def _run_tool(name: str, tool_input: dict[str, Any], auth_token: Optional[str]) -> str:
    """Execute a copilot tool by calling the platform's own REST API."""
    builder = _TOOL_ROUTES.get(name)
    if builder is None:
        return f"Error: unknown tool '{name}'."
    try:
        path = builder(tool_input or {})
    except Exception as exc:  # bad input shape
        return f"Error building request for {name}: {exc}"

    import httpx

    headers = {"Authorization": auth_token} if auth_token else {}
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=15.0) as http:
            resp = await http.get(path, headers=headers)
        if resp.status_code >= 400:
            return f"Tool {name} returned HTTP {resp.status_code}: {resp.text[:500]}"
        text = resp.text
    except Exception as exc:
        return f"Tool {name} failed: {exc}"

    if len(text) > _MAX_TOOL_RESULT_CHARS:
        text = text[:_MAX_TOOL_RESULT_CHARS] + " …(truncated)"
    return text


async def stream_reply(
    messages: list[dict[str, Any]],
    context: Optional[dict[str, Any]] = None,
    activity: Optional[list[str]] = None,
    auth_token: Optional[str] = None,
) -> AsyncIterator[str]:
    """Stream the copilot's reply, running tool calls between turns as needed."""
    convo = _sanitize_messages(messages)
    if not convo:
        yield "Ask me about the current plan, a truck, a client, or the KPIs on screen."
        return

    client = _get_client()
    system = build_system_prompt(context, activity)

    for _ in range(MAX_TOOL_ITERATIONS):
        async with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=convo,
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()

        if final.stop_reason != "tool_use":
            return

        # Record the assistant turn (text + tool_use blocks) verbatim.
        convo.append({"role": "assistant", "content": final.content})

        # Execute every requested tool and feed the results back.
        tool_results: list[dict[str, Any]] = []
        for block in final.content:
            if getattr(block, "type", None) == "tool_use":
                result = await _run_tool(block.name, block.input, auth_token)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
        convo.append({"role": "user", "content": tool_results})

    yield "\n\n[Stopped: reached the tool-call limit for this question.]"
