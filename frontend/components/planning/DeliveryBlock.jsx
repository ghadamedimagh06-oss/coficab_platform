import { useDraggable } from '@dnd-kit/core';
import { GripVertical, Lock, RotateCcw, X } from 'lucide-react';
import { WORK_START, WORK_END, toMinutes, toClock } from './timeline';

const PALETTE = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#14b8a6', '#f97316', '#a855f7'];

function clientColor(client) {
  const hash = String(client || '').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return PALETTE[hash % PALETTE.length];
}

function resizeTimes(delivery, edge, deltaMinutes) {
  const currentStart = toMinutes(delivery.etd);
  const currentEnd = Math.max(toMinutes(delivery.eta), currentStart + 30);
  if (edge === 'start') {
    const nextStart = Math.min(currentEnd - 30, Math.max(WORK_START, currentStart + deltaMinutes));
    return [toClock(nextStart), toClock(currentEnd)];
  }
  const nextEnd = Math.max(currentStart + 30, Math.min(WORK_END, currentEnd + deltaMinutes));
  return [toClock(currentStart), toClock(nextEnd)];
}

export default function DeliveryBlock({ delivery, onResize, onCancel, onRestore, minutesPerPixel = 1 }) {
  const locked = delivery.constraints?.required_truck_id || delivery.constraints?.time_window;
  const urgent = String(delivery.priority || '').toLowerCase() === 'urgent';
  const cancelled = delivery.status === 'cancelled';
  const positions = Number(delivery.quantity_positions || delivery.position_count || 0);
  const weight = Number(delivery.quantity_kg || 0);
  const base = clientColor(delivery.client);
  const rail = cancelled ? '#cbd5e1' : urgent ? '#ef4444' : locked ? '#f59e0b' : base;

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `delivery-${delivery.id}`,
    data: { deliveryId: delivery.id, delivery },
    disabled: cancelled,
  });
  const dragStyle = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    zIndex: isDragging ? 30 : undefined,
    opacity: isDragging ? 0.9 : undefined,
  } : undefined;

  function startResize(edge, event) {
    event.preventDefault();
    event.stopPropagation();
    if (!onResize || cancelled) return;

    const startX = event.clientX;
    const handleMove = (moveEvent) => {
      const deltaMinutes = Math.round(((moveEvent.clientX - startX) * minutesPerPixel) / 15) * 15;
      const [nextEtd, nextEta] = resizeTimes(delivery, edge, deltaMinutes);
      onResize(delivery.id, nextEtd, nextEta);
    };
    const stopResize = () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', stopResize);
      window.removeEventListener('pointercancel', stopResize);
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', stopResize);
    window.addEventListener('pointercancel', stopResize);
  }

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onContextMenu={(event) => {
        event.preventDefault();
        cancelled ? onRestore(delivery.id) : onCancel(delivery.id);
      }}
      className={`group relative flex h-full min-w-0 flex-col overflow-hidden rounded-xl border text-sm shadow-[0_1px_2px_rgba(26,26,46,0.06)] ring-1 ring-black/[0.02] transition-all duration-150 ${
        cancelled
          ? 'border-slate-200 bg-slate-50 text-slate-400'
          : 'border-[#ece8e1] bg-white text-ink hover:-translate-y-0.5 hover:shadow-[0_8px_20px_rgba(26,26,46,0.12)]'
      } ${cancelled ? 'cursor-default' : 'cursor-grab active:cursor-grabbing'}`}
      style={{
        background: cancelled
          ? undefined
          : `linear-gradient(180deg, ${base}14 0%, #ffffff 58%)`,
        touchAction: 'none',
        ...dragStyle,
      }}
      title={`${delivery.client} · ${delivery.etd || '--'}–${delivery.eta || '--'} · ${positions} pos${urgent ? ' · URGENT' : ''}${locked ? ' · locked' : ''}`}
    >
      {/* status / client colour rail */}
      <span className="pointer-events-none absolute left-0 top-0 bottom-0 w-1.5" style={{ backgroundColor: rail }} />

      {!cancelled && (
        <>
          <button
            type="button"
            aria-label="Resize start time"
            onPointerDown={(event) => startResize('start', event)}
            className="absolute left-0 top-1.5 bottom-1.5 z-10 flex w-3 cursor-ew-resize items-center justify-center text-ink/0 transition group-hover:text-ink/30"
            title="Resize start time"
          >
            <GripVertical size={10} />
          </button>
          <button
            type="button"
            aria-label="Resize end time"
            onPointerDown={(event) => startResize('end', event)}
            className="absolute right-0 top-1.5 bottom-1.5 z-10 flex w-3 cursor-ew-resize items-center justify-center text-ink/0 transition group-hover:text-ink/30"
            title="Resize end time"
          >
            <GripVertical size={10} />
          </button>
        </>
      )}

      <div className="flex items-start justify-between gap-1 pl-3.5 pr-2 pt-2">
        <span
          className="min-w-0 break-words text-[13px] font-semibold leading-tight"
          style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
        >
          {delivery.client}
        </span>
        <span className="flex shrink-0 items-center gap-0.5">
          {urgent && !cancelled && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold leading-none text-white" title="Urgent delivery">!</span>
          )}
          {locked && !cancelled ? (
            <span className="rounded-full p-0.5 text-amber-500" title="Hard constraint from Excel (locked time / truck)">
              <Lock size={12} />
            </span>
          ) : (
            <button
              type="button"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                cancelled ? onRestore(delivery.id) : onCancel(delivery.id);
              }}
              className="rounded-full p-0.5 text-[#9e9aa4] opacity-0 transition hover:bg-black/5 hover:text-ink group-hover:opacity-100"
              title={cancelled ? 'Restore delivery' : 'Cancel delivery'}
            >
              {cancelled ? <RotateCcw size={12} /> : <X size={12} />}
            </button>
          )}
        </span>
      </div>

      <div className="mt-auto flex items-center gap-1.5 pb-2 pl-3.5 pr-2 pt-1">
        <span className="inline-flex items-center rounded-md bg-black/[0.04] px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-[#4b4b5b]">
          {delivery.etd || '--'}–{delivery.eta || '--'}
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-muted">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: base }} />
          {positions.toLocaleString()} pos{weight ? ` · ${(weight / 1000).toFixed(1)} t` : ''}
        </span>
      </div>
    </div>
  );
}
