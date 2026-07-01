"""Optiroute — the in-app dispatch assistant (with tool access to the platform).

Turns the static "Assistant" panel into a real LLM copilot. Two grounding paths:

1. **Screen context** — the frontend sends a compact snapshot of whatever the
   dispatcher is currently looking at (active plan, KPI cards, fleet status,
   recent actions). We inject it into the system prompt so answers about the
   current screen are instant and concrete.
2. **Tools** — for questions that go beyond the current screen ("how's the whole
   fleet", "any open incidents", "what does the dashboard KPI say"), the model
   can call read-only tools that hit the platform's own REST API. This reuses
   every existing offline/mock fallback and the same data the UI sees.

The backend talks to any OpenAI-compatible chat endpoint. By default it targets
**Groq** (free, fast, Llama 3.3 70B), but it works unchanged against OpenAI,
Together, Ollama, etc. — just override the base URL / model / key via env:

    GROQ_API_KEY=gsk_...            # or COPILOT_API_KEY / OPENAI_API_KEY
    COPILOT_MODEL=llama-3.3-70b-versatile
    COPILOT_BASE_URL=https://api.groq.com/openai/v1

When no key is set the route degrades gracefully instead of 500-ing.
"""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Optional

# Default to Groq's free, fast Llama 3.3 70B. Override per-deployment if needed.
MODEL = os.getenv("COPILOT_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = int(os.getenv("COPILOT_MAX_TOKENS", "1024"))
# OpenAI-compatible endpoint the chat client talks to (Groq by default).
BASE_URL = os.getenv("COPILOT_BASE_URL", "https://api.groq.com/openai/v1")
# Base URL the copilot's tools call back into (this same backend).
API_BASE = os.getenv("COPILOT_API_BASE", "http://127.0.0.1:8000")
# Safety cap on the agentic loop so a tool-happy turn can't run forever.
MAX_TOOL_ITERATIONS = int(os.getenv("COPILOT_MAX_TOOL_ITERATIONS", "6"))

# Cap the injected screen context so an oversized page payload can't blow the prompt.
_MAX_CONTEXT_CHARS = 20_000
# Cap each tool result so a huge transports list can't blow the context either.
_MAX_TOOL_RESULT_CHARS = 16_000


def _api_key() -> str:
    """Resolve the API key from any of the supported env vars."""
    return (
        os.getenv("GROQ_API_KEY")
        or os.getenv("COPILOT_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()


_SYSTEM_PROMPT = """\
You are Optiroute, the dispatch assistant embedded in COFICAB's \
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
- The tools let you look up live data across the WHOLE platform: KPI cards and \
the daily Load Efficiency Rate/OTD dashboard, fleet (trucks/drivers/clients/utilization), the \
plan and transports, specific plan versions, pending oversized-delivery splits, \
incidents, live tracking and mission status, the four automation agents, dispatch \
logs and mission briefs, data/ingestion stats, and metrics trends/history. If no \
specific tool fits, use `query_platform` to GET any other read-only endpoint by \
path. Call a tool when the answer needs data that is not in the CONTEXT block; do \
not call tools for data already present in the context.

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

# --- Tool definitions (OpenAI function-calling format) -------------------------
# Read-only views of the platform's own REST API.

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_kpis",
            "description": (
                "Get the live operational KPIs exactly as shown on the dashboard, "
                "computed from the daily plan: Load Efficiency Rate, OTD, Load Efficiency, Fuel/Tonnage, "
                "plus totals (deliveries, positions, active trucks, distance, tonnage, "
                "unassigned). Use for any performance / on-time / KPI question. Optional "
                "day (YYYY-MM-DD) and period ('daily','weekly','monthly')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "Day as YYYY-MM-DD (optional, defaults to latest)."},
                    "period": {"type": "string", "description": "'daily' (default), 'weekly', or 'monthly'."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fleet",
            "description": (
                "List fleet resources. 'trucks' = vehicles with capacity/status, "
                "'drivers' = drivers with status, 'clients' = client directory, "
                "'utilization' = per-truck utilization. Use for fleet/driver/client questions."
            ),
            "parameters": {
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_transports",
            "description": (
                "List planned/active transport deliveries (the daily plan rows: "
                "client, truck, quantities, times, status). Optionally filter by day "
                "(YYYY-MM-DD). Use for questions about the plan, routes, or deliveries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {"type": "string", "description": "Day filter as YYYY-MM-DD (optional)."},
                    "limit": {"type": "integer", "description": "Max rows (default 200)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_incidents",
            "description": (
                "Get logistics incidents/alerts (breakdowns, delays, SLA risks). "
                "Set stats=true for aggregate counts instead of the list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stats": {"type": "boolean", "description": "Return aggregate stats instead of the list."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tracking_live",
            "description": "Get live tracking of in-flight transports (positions, ETAs, status).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_status",
            "description": "Get the status/health of the four background automation agents (collector, optimizer, monitor, notifier).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dispatch_logs",
            "description": "Get recent driver dispatch/notification logs (which mission briefs were sent and their status).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_stats",
            "description": "Get high-level counts of ingested data (clients, demands, trucks, drivers, plans). Use for 'how much data', coverage, or overview questions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_splits",
            "description": "List oversized deliveries awaiting a split decision (quantity exceeds a single truck). Use to flag planning risks or pending dispatcher actions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": (
                "Get a specific metrics series: 'weekly_deliveries' (delivery volume "
                "trend), 'efficiency_distribution' (utilization spread), 'timeline' "
                "(recent activity), 'daily_snapshot' / 'monthly_snapshot' (KPI snapshots). "
                "Use for trends and history beyond the current KPI cards."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "weekly_deliveries",
                            "efficiency_distribution",
                            "timeline",
                            "daily_snapshot",
                            "monthly_snapshot",
                        ],
                        "description": "Which metrics series to fetch.",
                    }
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plan",
            "description": "Get a specific plan version by id (the optimized routes for that run). Set kpis=true for that plan's KPI preview instead of the full plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_version_id": {"type": "string", "description": "The plan version id."},
                    "kpis": {"type": "boolean", "description": "Return the plan's KPI preview instead of the full plan."},
                },
                "required": ["plan_version_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_platform",
            "description": (
                "Escape hatch: fetch ANY other read-only platform endpoint by path when "
                "no specific tool above fits. Pass a GET path under /api/ — e.g. "
                "'/api/fleet/trucks/12', '/api/incidents/5', '/api/data/ingestion-history', "
                "'/api/tracking/missions/abc/status', '/api/planning/{plan_version_id}/changelog', "
                "'/api/dispatch/missions/{mission_id}/brief'. Prefer the specific tools when "
                "they exist; use this for by-id lookups and anything else. Read-only GET only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Platform API path starting with /api/ (may include a query string)."}
                },
                "required": ["path"],
            },
        },
    },
]

# Map tool name -> (HTTP path builder). Each returns a path string given the input.
_TOOL_ROUTES = {
    # The live dashboard KPIs (OTIF/OTD/Load/Fuel) computed from the daily plan —
    # the same source the dashboard UI shows. The ERD-table KPIs at
    # /api/metrics/kpi are only populated once monthly snapshots are computed.
    "get_kpis": lambda i: "/api/planning/daily/dashboard?" + _qs(
        {"day": i.get("day"), "period": i.get("period") or "daily"}
    ),
    "get_fleet": lambda i: f"/api/fleet/{i.get('kind', 'trucks')}",
    "get_transports": lambda i: "/api/data/transports?" + _qs(
        {"day": i.get("day"), "limit": i.get("limit") or 200}
    ),
    "get_incidents": lambda i: "/api/incidents/stats" if i.get("stats") else "/api/incidents",
    "get_tracking_live": lambda i: "/api/tracking/live",
    "get_agent_status": lambda i: "/api/agents/status",
    "get_dispatch_logs": lambda i: "/api/dispatch/logs",
    "get_data_stats": lambda i: "/api/data/stats",
    "get_pending_splits": lambda i: "/api/planning/oversized/pending",
    "get_metrics": lambda i: {
        "weekly_deliveries": "/api/metrics/deliveries/weekly",
        "efficiency_distribution": "/api/metrics/efficiency/distribution",
        "timeline": "/api/metrics/timeline",
        "daily_snapshot": "/api/metrics/kpi/snapshot/daily",
        "monthly_snapshot": "/api/metrics/kpi/snapshot/monthly",
    }.get(i.get("kind") or "timeline", "/api/metrics/timeline"),
    "get_plan": lambda i: f"/api/optimization/plan/{i.get('plan_version_id')}"
    + ("/kpis" if i.get("kpis") else ""),
    "query_platform": lambda i: _safe_get_path(i),
}


def _qs(params: dict[str, Any]) -> str:
    from urllib.parse import urlencode

    return urlencode({k: v for k, v in params.items() if v not in (None, "")})


# Path prefixes the generic query_platform tool may NEVER touch (credentials / self).
_BLOCKED_PREFIXES = ("/api/auth", "/api/copilot")


def _safe_get_path(i: dict[str, Any]) -> str:
    """Validate an arbitrary GET path for the generic query_platform escape hatch."""
    path = (i.get("path") or "").strip()
    if not path.startswith("/api/"):
        raise ValueError("path must be a platform endpoint starting with /api/")
    low = path.split("?", 1)[0].lower()
    if any(low.startswith(p) for p in _BLOCKED_PREFIXES):
        raise ValueError("that endpoint is not accessible to the assistant")
    return path


_client = None


def _get_client():
    """Lazily build a shared AsyncOpenAI client pointed at the configured endpoint."""
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=_api_key(), base_url=BASE_URL)
    return _client


def is_configured() -> bool:
    """True when an API credential is available in the environment."""
    return bool(_api_key())


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
        # Generous timeout: get_kpis hits the daily dashboard, which runs the
        # OR-Tools optimizer (~12s cold, cached after).
        async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as http:
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
    convo = [{"role": "system", "content": system}, *convo]

    for _ in range(MAX_TOOL_ITERATIONS):
        # parallel_tool_calls=False: Llama-on-Groq frequently emits malformed
        # *parallel* tool calls (HTTP 400 tool_use_failed). One tool per turn is
        # fine — the agentic loop fans out across iterations instead.
        try:
            stream = await client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=convo,
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=False,
                stream=True,
            )
        except Exception:
            # Some endpoints/models reject parallel_tool_calls; retry without it.
            stream = await client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=convo,
                tools=TOOLS,
                tool_choice="auto",
                stream=True,
            )

        text_acc = ""
        # index -> {"id", "name", "arguments"} accumulated across streamed deltas
        tool_calls: dict[int, dict[str, str]] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                text_acc += delta.content
                yield delta.content
            for tc in getattr(delta, "tool_calls", None) or []:
                entry = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    entry["id"] = tc.id
                if tc.function and tc.function.name:
                    entry["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    entry["arguments"] += tc.function.arguments

        # No tool calls -> the model is done answering.
        if not tool_calls:
            return

        # Record the assistant turn (text + tool_calls), then run each tool.
        convo.append(
            {
                "role": "assistant",
                "content": text_acc or None,
                "tool_calls": [
                    {
                        "id": e["id"],
                        "type": "function",
                        "function": {"name": e["name"], "arguments": e["arguments"] or "{}"},
                    }
                    for e in tool_calls.values()
                ],
            }
        )
        for e in tool_calls.values():
            try:
                args = json.loads(e["arguments"] or "{}")
            except (TypeError, ValueError):
                args = {}
            result = await _run_tool(e["name"], args, auth_token)
            convo.append({"role": "tool", "tool_call_id": e["id"], "content": result})

    yield "\n\n[Stopped: reached the tool-call limit for this question.]"
