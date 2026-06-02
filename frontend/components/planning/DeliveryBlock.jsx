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
  const positions = Number(delivery.quantity_positions || delivery.position_count || 0);
  const weight = Number(delivery.quantity_kg || 0);
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
      className={`relative h-full min-w-0 rounded-2xl border px-4 py-3 text-sm shadow-sm transition ${
        delivery.status === 'cancelled'
          ? 'border-slate-300 bg-slate-100 text-slate-500 opacity-70'
          : 'border-[#d8d3ca] text-[#1a1a2e] hover:-translate-y-0.5 hover:shadow-md'
      } ${delivery.status === 'cancelled' ? 'cursor-default' : 'cursor-grab active:cursor-grabbing'}`}
      style={{
        backgroundColor: delivery.status === 'cancelled' ? undefined : clientColor(delivery.client),
        touchAction: 'none',
        ...dragStyle,
      }}
      title={`${delivery.client} ${delivery.etd || ''}-${delivery.eta || ''}`}
    >
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
      <div className="flex items-start justify-between gap-2">
        <span className={`overflow-hidden break-words font-semibold leading-tight ${compact ? 'max-h-10' : 'max-h-14'}`}>{delivery.client}</span>
        {locked && delivery.status !== 'cancelled' ? (
          <span className="shrink-0 rounded-full p-1" title="Hard constraint from Excel">
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
            className="shrink-0 rounded-full p-1 hover:bg-white/50"
            title={delivery.status === 'cancelled' ? 'Restore delivery' : 'Cancel delivery'}
          >
            {delivery.status === 'cancelled' ? <RotateCcw size={12} /> : <X size={12} />}
          </button>
        )}
      </div>
      <div className="mt-2 text-xs text-[#6b6b7b]">{delivery.etd || '--'} to {delivery.eta || '--'}</div>
      <div className="mt-1 text-xs text-[#6b6b7b]">
        {positions.toLocaleString()} pos{weight ? ` / ${weight.toLocaleString()} kg` : ''}
      </div>
    </div>
  );
}
