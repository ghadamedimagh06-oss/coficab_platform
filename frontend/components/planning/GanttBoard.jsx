import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDraggable,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import TimeAxis from './TimeAxis';
import TruckLane from './TruckLane';
import { WORK_START, WORK_MINUTES, SNAP_MINUTES } from './timeline';

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
      className="inline-flex cursor-grab items-center gap-2 rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-600 shadow-sm active:cursor-grabbing"
      style={{ touchAction: 'none', ...style }}
    >
      <span className="h-5 w-3 rounded-sm border border-red-300 bg-[repeating-linear-gradient(135deg,#ef4444_0,#ef4444_3px,#fee2e2_3px,#fee2e2_6px)]" />
      Manual marker
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
  const hasStops = (plan?.trucks || []).some((truck) => (truck.trips || []).some((trip) => (trip.stops || []).length > 0));
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

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
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-4 text-xs text-[#6b6b7b]">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-1.5 rounded-sm bg-[#ef4444]" /> Urgent
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-1.5 rounded-sm bg-[#f59e0b]" /> Locked (Excel constraint)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm border border-[#d8d3ca] bg-[#bbf7d0]" /> Colour = client
          </span>
        </div>
        <MarkerTool />
      </div>
      <div className="overflow-x-auto rounded-[2rem] border border-[#e8e5df] bg-white shadow-sm">
        <div className="min-w-[1800px]">
          <TimeAxis />
          {(plan?.trucks || []).map((truck) => (
            <TruckLane
              key={truck.truck_id}
              truck={truck}
              markers={plan?.manual_markers || []}
              onResizeDelivery={onResizeDelivery}
              onCancel={onCancel}
              onRestore={onRestore}
              onDeleteMarker={onDeleteMarker}
            />
          ))}
          {plan && !hasStops && (
            <div className="px-6 py-10 text-sm text-[#6b6b7b]">No deliveries could be placed on this day.</div>
          )}
        </div>
      </div>
    </DndContext>
  );
}
