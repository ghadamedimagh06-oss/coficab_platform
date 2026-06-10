import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDraggable,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { Warehouse } from 'lucide-react';
import TimeAxis from './TimeAxis';
import TruckLane from './TruckLane';
import { WORK_START, WORK_END, WORK_MINUTES, SNAP_MINUTES } from './timeline';

function MarkerTool() {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: 'marker-template',
    data: { markerTemplate: true },
  });
  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    opacity: isDragging ? 0.8 : undefined,
    zIndex: isDragging ? 40 : undefined,
  } : undefined;

  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...listeners}
      className="inline-flex cursor-grab items-center gap-2 rounded-full border border-red-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-red-600 shadow-sm transition hover:bg-red-50 active:cursor-grabbing"
      style={{ touchAction: 'none', ...style }}
    >
      <span className="h-4 w-2.5 rounded-sm border border-red-300 bg-[repeating-linear-gradient(135deg,#ef4444_0,#ef4444_3px,#fee2e2_3px,#fee2e2_6px)]" />
      Drag a blocking marker
    </button>
  );
}

function snappedMinuteFromDrag(event) {
  const overRect = event.over?.rect;
  if (!overRect?.width) return WORK_START;

  const translated = event.active?.rect?.current?.translated;
  const initial = event.active?.rect?.current?.initial;
  const left = translated?.left ?? initial?.left ?? overRect.left;
  const ratio = Math.max(0, Math.min(1, (left - overRect.left) / overRect.width));
  return WORK_START + Math.round((ratio * WORK_MINUTES) / SNAP_MINUTES) * SNAP_MINUTES;
}

function LegendChip({ swatch, children }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[#6b6b7b]">
      {swatch}
      {children}
    </span>
  );
}

export default function GanttBoard({
  plan,
  onDropDelivery,
  onResizeDelivery,
  onCancel,
  onRestore,
  onDropMarker,
  onMoveMarker,
  onDeleteMarker,
}) {
  const trucks = plan?.trucks || [];
  const hasStops = trucks.some((truck) => (truck.trips || []).some((trip) => (trip.stops || []).length > 0));
  const activeTrucks = trucks.filter((t) => (t.trips || []).some((tr) => (tr.stops || []).length > 0)).length;
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  // Live "now" marker, but only when the board is showing today's plan.
  const today = new Date().toISOString().slice(0, 10);
  const nowMin = new Date().getHours() * 60 + new Date().getMinutes();
  const nowMinute = plan?.day === today && nowMin >= WORK_START && nowMin <= WORK_END ? nowMin : null;

  function handleDragEnd(event) {
    const targetTruckId = event.over?.data?.current?.truckId;
    const activeData = event.active?.data?.current || {};
    if (!targetTruckId) return;
    const targetMinute = snappedMinuteFromDrag(event);

    if (activeData.markerTemplate) {
      onDropMarker?.(targetTruckId, targetMinute);
      return;
    }
    if (activeData.markerId) {
      onMoveMarker?.(activeData.markerId, targetTruckId, targetMinute);
      return;
    }
    if (activeData.deliveryId) {
      onDropDelivery(activeData.deliveryId, targetTruckId, targetMinute);
    }
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <div className="overflow-hidden rounded-[1.75rem] border border-[#ece8e1] bg-white shadow-[0_2px_16px_rgba(26,26,46,0.04)]">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#ece8e1] bg-[#fcfbf9] px-5 py-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <h3 className="text-sm font-semibold text-[#1a1a2e]">Truck timeline</h3>
            <span className="rounded-full bg-[#7c3aed]/10 px-2 py-0.5 text-[11px] font-semibold text-[#7c3aed]">
              {activeTrucks} active
            </span>
            <span className="hidden h-4 w-px bg-[#ece8e1] sm:block" />
            <div className="hidden flex-wrap items-center gap-3.5 sm:flex">
              <LegendChip swatch={<span className="h-3 w-1.5 rounded-sm bg-[#ef4444]" />}>Urgent</LegendChip>
              <LegendChip swatch={<span className="h-3 w-1.5 rounded-sm bg-[#f59e0b]" />}>Locked</LegendChip>
              <LegendChip swatch={<span className="h-2.5 w-2.5 rounded-full bg-gradient-to-br from-[#8b5cf6] to-[#3b82f6]" />}>Colour = client</LegendChip>
              <LegendChip swatch={<Warehouse size={11} className="text-[#7c3aed]" />}>COFICAB depart / return</LegendChip>
            </div>
          </div>
          <MarkerTool />
        </div>

        {/* Scrollable board */}
        <div className="overflow-x-auto">
          <div className="min-w-[1900px]">
            <TimeAxis nowMinute={nowMinute} />
            {trucks.map((truck) => (
              <TruckLane
                key={truck.truck_id}
                truck={truck}
                markers={plan?.manual_markers || []}
                nowMinute={nowMinute}
                onResizeDelivery={onResizeDelivery}
                onCancel={onCancel}
                onRestore={onRestore}
                onDeleteMarker={onDeleteMarker}
              />
            ))}
            {plan && !hasStops && (
              <div className="px-6 py-12 text-center text-sm text-[#9e9aa4]">No deliveries could be placed on this day.</div>
            )}
          </div>
        </div>
      </div>
    </DndContext>
  );
}
