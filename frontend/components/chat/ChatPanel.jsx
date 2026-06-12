"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { getCopilotStatus, streamCopilotChat } from "../../app/services/api";

/**
 * In-app Claude-powered Dispatch Copilot.
 *
 * Backward compatible: pages still pass `messages` (an array of activity
 * strings). Those become the assistant's "recent actions" context and seed the
 * panel. New optional props:
 *   - context: a compact snapshot of the current screen (plan, KPIs, fleet) so
 *     Claude answers grounded in real data.
 *   - title: heading label.
 */
export default function ChatPanel({ messages = [], context = null, title = "Dispatch Copilot", fill = false }) {
  const activity = Array.isArray(messages) ? messages.filter((m) => typeof m === "string") : [];
  const [configured, setConfigured] = useState(null); // null = unknown
  const [conversation, setConversation] = useState([]); // {role, content}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let alive = true;
    getCopilotStatus()
      .then((s) => alive && setConfigured(Boolean(s?.configured)))
      .catch(() => alive && setConfigured(false));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [conversation, busy]);

  async function handleSend(e) {
    e?.preventDefault?.();
    const text = input.trim();
    if (!text || busy) return;

    setError(null);
    setInput("");
    const nextConversation = [...conversation, { role: "user", content: text }];
    // Add an empty assistant bubble we stream tokens into.
    setConversation([...nextConversation, { role: "assistant", content: "" }]);
    setBusy(true);

    try {
      await streamCopilotChat(nextConversation, {
        context,
        activity,
        onToken: (chunk) => {
          setConversation((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            if (last && last.role === "assistant") {
              copy[copy.length - 1] = { ...last, content: last.content + chunk };
            }
            return copy;
          });
        },
      });
    } catch (err) {
      setError(err?.message || "Copilot request failed.");
      setConversation((prev) => prev.slice(0, -1)); // drop the empty assistant bubble
    } finally {
      setBusy(false);
    }
  }

  const suggestions = [
    "Summarize today's plan",
    "Any risks or late deliveries?",
    "Why is this route ordered this way?",
  ];

  return (
    <aside
      className={`rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl shadow-black/10 flex flex-col ${
        fill ? "h-full" : "max-h-[40rem]"
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-2xl bg-gradient-to-br from-[#7c3aed] to-[#5b21b6] text-white">
            <Sparkles size={18} />
          </span>
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-[var(--muted)]">Copilot</p>
            <h2 className="text-lg font-semibold text-[var(--text)]">{title}</h2>
          </div>
        </div>
        {configured === false && (
          <span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-semibold text-amber-700">
            Not configured
          </span>
        )}
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto scrollbar-thin pr-1">
        {conversation.length === 0 && (
          <div className="rounded-3xl border border-[var(--border)] bg-[var(--card)] p-4 text-[var(--muted)]">
            <p className="text-sm">
              Ask the assistant about the current plan, a truck, a client, or the KPIs on screen.
              It can summarize the plan, flag risks, and explain optimizer decisions.
            </p>
            {activity.length > 0 && (
              <div className="mt-3 border-t border-[var(--border)] pt-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Recent activity</p>
                <ul className="mt-2 space-y-1 text-xs">
                  {activity.slice(-5).map((item, i) => (
                    <li key={i} className="text-[var(--text)]">• {item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {conversation.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
                msg.role === "user"
                  ? "bg-[#7c3aed] text-white"
                  : "border border-[var(--border)] bg-[var(--card)] text-[var(--text)]"
              }`}
            >
              {msg.content || (busy && index === conversation.length - 1 ? "…" : "")}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="mt-2 text-xs text-red-500">{error}</p>}

      {conversation.length === 0 && configured !== false && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setInput(s)}
              className="rounded-full border border-[var(--border)] bg-[var(--card)] px-3 py-1 text-xs text-[var(--muted)] hover:text-[var(--text)] transition"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSend} className="mt-3 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={configured === false || busy}
          placeholder={
            configured === false
              ? "Set ANTHROPIC_API_KEY to enable the copilot"
              : "Ask the dispatch copilot…"
          }
          className="flex-1 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--text)] outline-none focus:border-[#7c3aed] disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={configured === false || busy || !input.trim()}
          className="grid h-10 w-10 place-items-center rounded-2xl bg-[#7c3aed] text-white transition hover:bg-[#6d28d9] disabled:opacity-40"
          aria-label="Send"
        >
          <Send size={18} />
        </button>
      </form>
    </aside>
  );
}
