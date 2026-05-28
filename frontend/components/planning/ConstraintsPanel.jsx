import { Lock, AlertTriangle } from 'lucide-react';

export default function ConstraintsPanel({ plan, onRestore }) {
  const deliveries = [
    ...(plan?.trucks || []).flatMap((truck) => (truck.trips || []).flatMap((trip) => trip.stops || [])),
    ...(plan?.unassigned || []),
  ];
  const constrained = deliveries.filter((delivery) => {
    const c = delivery.constraints || {};
    return c.required_truck_id || c.required_driver || c.time_window || c.comment_constraint || delivery.status === 'cancelled';
  });

  return (
    <aside className="sticky top-6 max-h-[calc(100vh-3rem)] overflow-y-auto rounded-[2rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Lock size={16} className="text-[#7c3aed]" />
        <h2 className="text-lg font-semibold text-[#1a1a2e]">Constraints</h2>
      </div>
      <div className="space-y-3">
        {constrained.length === 0 && (
          <p className="text-sm text-[#6b6b7b]">No hard constraints in the selected plan.</p>
        )}
        {constrained.map((delivery) => (
          <div key={delivery.id} className="rounded-2xl border border-[#e8e5df] bg-[#f8f7f3] p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-[#1a1a2e]">{delivery.client} #{delivery.id}</p>
                <p className="mt-1 text-xs text-[#6b6b7b]">
                  {delivery.constraints?.time_window ? `Window ${delivery.constraints.time_window[0]}-${delivery.constraints.time_window[1]}` : 'Flexible window'}
                </p>
                <p className="mt-1 text-xs text-[#6b6b7b]">
                  {Number(delivery.quantity_positions || delivery.position_count || 0).toLocaleString()} positions
                  {delivery.quantity_kg ? ` / ${Number(delivery.quantity_kg).toLocaleString()} kg` : ''}
                </p>
                {delivery.constraints?.required_truck_id && (
                  <p className="mt-1 text-xs text-[#6b6b7b]">Truck {delivery.constraints.required_truck_id} only</p>
                )}
                {delivery.constraints?.required_driver && (
                  <p className="mt-1 text-xs text-[#6b6b7b]">Driver {delivery.constraints.required_driver}</p>
                )}
                {delivery.constraints?.required_departure && (
                  <p className="mt-1 text-xs text-[#6b6b7b]">Departure {delivery.constraints.required_departure}</p>
                )}
                {delivery.constraints?.comment_constraint && (
                  <p className="mt-2 text-xs font-semibold text-red-600">{delivery.constraints.comment_constraint}</p>
                )}
              </div>
              {delivery.status === 'cancelled' && <AlertTriangle size={16} className="text-red-500" />}
            </div>
            {delivery.status === 'cancelled' && (
              <button
                type="button"
                onClick={() => onRestore(delivery.id)}
                className="mt-3 rounded-full border border-[#e8e5df] bg-white px-3 py-1 text-xs font-semibold text-[#1a1a2e]"
              >
                Restore
              </button>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
