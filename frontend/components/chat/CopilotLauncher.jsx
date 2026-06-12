"use client";

import { useState } from "react";
import { MessageSquare, X } from "lucide-react";
import ChatPanel from "./ChatPanel";

/**
 * Global floating Copilot. Rendered once in AppShell so the assistant is
 * reachable from every page (including the dashboard, which has no inline
 * panel). The copilot has tool access, so it can answer fleet/KPI/plan
 * questions even without page-specific context.
 */
export default function CopilotLauncher() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Floating launch button */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 rounded-full bg-gradient-to-br from-[#7c3aed] to-[#5b21b6] px-5 py-3 text-sm font-semibold text-white shadow-xl shadow-black/20 transition hover:scale-105"
          aria-label="Open Dispatch Copilot"
        >
          <MessageSquare size={18} />
          Copilot
        </button>
      )}

      {/* Slide-over drawer */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="fixed bottom-0 right-0 top-0 z-50 flex w-full max-w-md flex-col p-4">
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="grid h-9 w-9 place-items-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] shadow-sm"
                aria-label="Close Copilot"
              >
                <X size={18} />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <ChatPanel title="Dispatch Copilot" context={{ page: "global" }} fill />
            </div>
          </div>
        </>
      )}
    </>
  );
}
