"use client";

export default function ChatPanel({ messages = [] }) {
  return (
    <aside className="mt-6 rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl shadow-black/10 max-h-[36rem] overflow-y-auto scrollbar-thin">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-[var(--muted)]">Copilot</p>
          <h2 className="text-lg font-semibold text-[var(--text)]">Assistant</h2>
        </div>
      </div>
      <div className="space-y-4">
        {messages.length === 0 ? (
          <div className="rounded-3xl border border-[var(--border)] bg-[var(--card)] p-4 text-[var(--muted)]">
            <p className="text-sm">Actions and optimization events appear here. The assistant will summarize your changes and highlight risks.</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={index} className="rounded-3xl border border-[var(--border)] bg-[var(--card)] p-4">
              <p className="text-sm text-[var(--text)]">{message}</p>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
