import TimeAxis from './TimeAxis';
import TruckLane from './TruckLane';

export default function GanttBoard({ plan, onDropDelivery, onCancel, onRestore }) {
  const hasStops = (plan?.trucks || []).some((truck) => (truck.trips || []).some((trip) => (trip.stops || []).length > 0));

  return (
    <div className="overflow-x-auto rounded-[2rem] border border-[#e8e5df] bg-white shadow-sm">
      <div className="min-w-[1800px]">
        <TimeAxis />
        {(plan?.trucks || []).map((truck) => (
          <TruckLane
            key={truck.truck_id}
            truck={truck}
            onDropDelivery={onDropDelivery}
            onCancel={onCancel}
            onRestore={onRestore}
          />
        ))}
        {plan && !hasStops && (
          <div className="px-6 py-10 text-sm text-[#6b6b7b]">No deliveries could be placed on this day.</div>
        )}
      </div>
    </div>
  );
}
