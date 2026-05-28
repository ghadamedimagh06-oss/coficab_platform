import { Lock, X, RotateCcw } from 'lucide-react';

const PALETTE = ['#ddd6fe', '#bfdbfe', '#bbf7d0', '#fde68a', '#fecaca', '#99f6e4', '#fed7aa', '#e9d5ff'];

function clientColor(client) {
  const hash = String(client || '').split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return PALETTE[hash % PALETTE.length];
}

export default function DeliveryBlock({ delivery, onCancel, onRestore, compact = false }) {
  const locked = delivery.constraints?.required_truck_id || delivery.constraints?.time_window;
  const fixedTruck = delivery.constraints?.required_truck_id;
  const positions = Number(delivery.quantity_positions || delivery.position_count || 0);
  const weight = Number(delivery.quantity_kg || 0);

  return (
    <div
      draggable={delivery.status !== 'cancelled' && !fixedTruck}
      onDragStart={(event) => event.dataTransfer.setData('delivery-id', String(delivery.id))}
      onContextMenu={(event) => {
        event.preventDefault();
        delivery.status === 'cancelled' ? onRestore(delivery.id) : onCancel(delivery.id);
      }}
      className={`h-full min-w-0 rounded-2xl border px-4 py-3 text-sm shadow-sm transition ${
        delivery.status === 'cancelled'
          ? 'border-slate-300 bg-slate-100 text-slate-500 opacity-70'
          : 'border-[#d8d3ca] text-[#1a1a2e] hover:-translate-y-0.5 hover:shadow-md'
      } ${locked ? 'cursor-not-allowed' : 'cursor-grab active:cursor-grabbing'}`}
      style={{
        backgroundColor: delivery.status === 'cancelled' ? undefined : clientColor(delivery.client),
      }}
      title={`${delivery.client} ${delivery.etd || ''}-${delivery.eta || ''}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`overflow-hidden break-words font-semibold leading-tight ${compact ? 'max-h-10' : 'max-h-14'}`}>{delivery.client}</span>
        {locked && delivery.status !== 'cancelled' ? (
          <span className="shrink-0 rounded-full p-1" title="Hard constraint from Excel">
            <Lock size={12} />
          </span>
        ) : (
          <button
            type="button"
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
