import { useDraggable } from '@dnd-kit/core';
import { GripVertical, Lock, RotateCcw, X } from 'lucide-react';
import { WORK_START, WORK_END, toMinutes, toClock } from './timeline';

const PALETTE = ['#ddd6fe', '#bfdbfe', '#bbf7d0', '#fde68a', '#fecaca', '#99f6e4', '#fed7aa', '#e9d5ff'];

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

export default function DeliveryBlock({ delivery, onResize, onCancel, onRestore, minutesPerPixel = 1, compact = false }) {
  const locked = delivery.constraints?.required_truck_id || delivery.constraints?.time_window;
  const urgent = String(delivery.priority || '').toLowerCase() === 'urgent';
  const positions = Number(delivery.quantity_positions || delivery.position_count || 0);
  const weight = Number(delivery.quantity_kg || 0);
  const accent = delivery.status === 'cancelled'
    ? null
    : urgent
      ? '#ef4444'
      : locked
        ? '#f59e0b'
        : null;
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `delivery-${delivery.id}`,
    data: { deliveryId: delivery.id, delivery },
    disabled: delivery.status === 'cancelled',
  });
  const dragStyle = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    zIndex: isDragging ? 30 : undefined,
    opacity: isDragging ? 0.85 : undefined,
  } : undefined;

  function startResize(edge, event) {
    event.preventDefault();
    event.stopPropagation();
    if (!onResize || delivery.status === 'cancelled') return;

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
        delivery.status === 'cancelled' ? onRestore(delivery.id) : onCancel(delivery.id);
      }}
      className={`relative flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border pl-4 pr-2.5 py-2 text-sm shadow-sm transition ${
        delivery.status === 'cancelled'
          ? 'border-slate-300 bg-slate-100 text-slate-500 opacity-70'
          : 'border-[#d8d3ca] text-[#1a1a2e] hover:-translate-y-0.5 hover:shadow-md'
      } ${delivery.status === 'cancelled' ? 'cursor-default' : 'cursor-grab active:cursor-grabbing'}`}
      style={{
        backgroundColor: delivery.status === 'cancelled' ? undefined : clientColor(delivery.client),
        touchAction: 'none',
        ...dragStyle,
      }}
      title={`${delivery.client} · ${delivery.etd || '--'}–${delivery.eta || '--'} · ${positions} pos${urgent ? ' · URGENT' : ''}${locked ? ' · locked' : ''}`}
    >
      {accent && (
        <span
          className="pointer-events-none absolute left-0 top-0 bottom-0 w-1.5 rounded-l-2xl"
          style={{ backgroundColor: accent }}
        />
      )}
      {delivery.status !== 'cancelled' && (
        <>
          <button
            type="button"
            aria-label="Resize start time"
            onPointerDown={(event) => startResize('start', event)}
            className="absolute left-0 top-2 bottom-2 flex w-3 cursor-ew-resize items-center justify-center rounded-l-2xl text-[#1a1a2e]/40 hover:bg-white/50"
            title="Resize start time"
          >
            <GripVertical size={10} />
          </button>
          <button
            type="button"
            aria-label="Resize end time"
            onPointerDown={(event) => startResize('end', event)}
            className="absolute right-0 top-2 bottom-2 flex w-3 cursor-ew-resize items-center justify-center rounded-r-2xl text-[#1a1a2e]/40 hover:bg-white/50"
            title="Resize end time"
          >
            <GripVertical size={10} />
          </button>
        </>
      )}
      <div className="flex items-start justify-between gap-1">
        <span
          className="min-w-0 break-words text-[13px] font-semibold leading-tight"
          style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
        >
          {delivery.client}
        </span>
        <span className="flex shrink-0 items-center gap-0.5">
          {urgent && delivery.status !== 'cancelled' && (
            <span className="rounded bg-red-500 px-1 py-0.5 text-[9px] font-bold uppercase leading-none text-white" title="Urgent delivery">
              !
            </span>
          )}
          {locked && delivery.status !== 'cancelled' ? (
            <span className="rounded-full p-0.5 text-amber-600" title="Hard constraint from Excel (locked time / truck)">
              <Lock size={12} />
            </span>
          ) : (
            <button
              type="button"
              onPointerDown={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation();
                delivery.status === 'cancelled' ? onRestore(delivery.id) : onCancel(delivery.id);
              }}
              className="rounded-full p-0.5 hover:bg-white/60"
              title={delivery.status === 'cancelled' ? 'Restore delivery' : 'Cancel delivery'}
            >
              {delivery.status === 'cancelled' ? <RotateCcw size={12} /> : <X size={12} />}
            </button>
          )}
        </span>
      </div>
      <div className="mt-auto pt-1 leading-tight">
        <div className="text-[11px] tabular-nums text-[#6b6b7b]">{delivery.etd || '--'} – {delivery.eta || '--'}</div>
        <div className="text-[11px] font-semibold text-[#4b4b5b]">
          {positions.toLocaleString()} pos{weight ? ` · ${weight.toLocaleString()} kg` : ''}
        </div>
      </div>
    </div>
  );
}
