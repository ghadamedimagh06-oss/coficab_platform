import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import TimeAxis from './TimeAxis';
import TruckLane from './TruckLane';
import { WORK_START, WORK_MINUTES, SNAP_MINUTES } from './timeline';

function snappedMinuteFromDrag(event) {
  const overRect = event.over?.rect;
  if (!overRect?.width) return WORK_START;

  const translated = event.active?.rect?.current?.translated;
  const initial = event.active?.rect?.current?.initial;
  const left = translated?.left ?? initial?.left ?? overRect.left;
  const ratio = Math.max(0, Math.min(1, (left - overRect.left) / overRect.width));
  return WORK_START + Math.round((ratio * WORK_MINUTES) / SNAP_MINUTES) * SNAP_MINUTES;
}

export default function GanttBoard({ plan, onDropDelivery, onResizeDelivery, onCancel, onRestore }) {
  const hasStops = (plan?.trucks || []).some((truck) => (truck.trips || []).some((trip) => (trip.stops || []).length > 0));
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  function handleDragEnd(event) {
    const targetTruckId = event.over?.data?.current?.truckId;
    const deliveryId = event.active?.data?.current?.deliveryId;
    if (!targetTruckId || !deliveryId) return;
    onDropDelivery(deliveryId, targetTruckId, snappedMinuteFromDrag(event));
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <div className="overflow-x-auto rounded-[2rem] border border-[#e8e5df] bg-white shadow-sm">
        <div className="min-w-[1800px]">
          <TimeAxis />
          {(plan?.trucks || []).map((truck) => (
            <TruckLane
              key={truck.truck_id}
              truck={truck}
              onResizeDelivery={onResizeDelivery}
              onCancel={onCancel}
              onRestore={onRestore}
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
