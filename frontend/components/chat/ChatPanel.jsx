"use client";

export default function ChatPanel({ messages = [] }) {
  return (
    <aside className="mt-6 rounded-3xl border border-slate-800 bg-slate-900/95 p-4 shadow-xl shadow-black/20 max-h-[36rem] overflow-y-auto scrollbar-thin">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Copilot</p>
          <h2 className="text-lg font-semibold">Assistant</h2>
        </div>
      </div>
      <div className="space-y-4">
        {messages.length === 0 ? (
          <div className="rounded-3xl border border-slate-800 bg-slate-950/90 p-4 text-slate-400">
            <p className="text-sm">Actions and optimization events appear here. The assistant will summarize your changes and highlight risks.</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={index} className="rounded-3xl border border-slate-800 bg-slate-950/90 p-4">
              <p className="text-sm text-slate-300">{message}</p>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
