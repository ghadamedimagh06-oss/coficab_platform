import { useCallback, useEffect, useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import DeliveryBlock from './DeliveryBlock';
import DepotMarker from './DepotMarker';

function minutes(value) {
  if (!value) return 480;
  const [h, m] = String(value).split(':').map(Number);
  return h * 60 + (m || 0);
}

function pct(value) {
  return Math.max(0, Math.min(100, ((minutes(value) - 480) / 540) * 100));
}

function deliveryBox(delivery) {
  const start = minutes(delivery.etd);
  const end = Math.max(minutes(delivery.eta), start + 30);
  const duration = Math.max(30, end - start);
  return {
    ...delivery,
    _start: start,
    _end: end,
    _left: ((start - 480) / 540) * 100,
    _width: Math.max((duration / 540) * 100, 8),
  };
}

function packedStops(stops) {
  const rows = [];
  return stops
    .map(deliveryBox)
    .sort((a, b) => a._start - b._start)
    .map((stop) => {
      let rowIndex = rows.findIndex((rowEnd) => stop._start >= rowEnd + 5);
      if (rowIndex === -1) {
        rowIndex = rows.length;
        rows.push(stop._end);
      } else {
        rows[rowIndex] = stop._end;
      }
      return { ...stop, _row: rowIndex, _rowCount: rows.length };
    });
}

export default function TruckLane({ truck, onResizeDelivery, onCancel, onRestore }) {
  const { isOver, setNodeRef } = useDroppable({
    id: `truck-lane-${truck.truck_id}`,
    data: { truckId: truck.truck_id },
  });
  const [laneNode, setLaneNode] = useState(null);
  const [laneWidth, setLaneWidth] = useState(0);
  const setTimelineRef = useCallback((node) => {
    setNodeRef(node);
    setLaneNode(node);
  }, [setNodeRef]);

  useEffect(() => {
    if (!laneNode) return undefined;
    const updateWidth = () => setLaneWidth(laneNode.getBoundingClientRect().width);
    updateWidth();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateWidth);
      return () => window.removeEventListener('resize', updateWidth);
    }
    const observer = new ResizeObserver(updateWidth);
    observer.observe(laneNode);
    return () => observer.disconnect();
  }, [laneNode]);

  const trips = truck.trips || [];
  const allStops = trips.flatMap((trip) => trip.stops || []);
  const packed = packedStops(allStops);
  const rowCount = Math.max(1, packed.reduce((max, stop) => Math.max(max, stop._row + 1), 1));
  const laneHeight = Math.max(118, rowCount * 94 + 24);
  const minutesPerPixel = laneWidth ? 540 / laneWidth : 1;

  return (
    <div className="grid grid-cols-[10rem_1fr] border-b border-[#e8e5df] last:border-b-0" style={{ minHeight: laneHeight }}>
      <div className="flex items-center border-r border-[#e8e5df] bg-white px-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#1a1a2e]">{truck.truck_label}</p>
          <p className="text-xs text-[#6b6b7b]">{Number(truck.capacity_positions || 0).toLocaleString()} positions</p>
          <p className="text-xs text-[#6b6b7b]">{Number(truck.capacity_kg || 0).toLocaleString()} kg</p>
        </div>
      </div>
      <div
        ref={setTimelineRef}
        className={`relative bg-[linear-gradient(to_right,#e8e5df_1px,transparent_1px)] transition-colors ${isOver ? 'bg-[#faf8f5]' : ''}`}
        style={{ backgroundSize: '11.111% 100%' }}
      >
        {allStops.length > 0 && (
          <>
            {trips.map((trip) => (
              <div key={`${trip.trip_id}-markers`}>
                <DepotMarker left={pct(trip.depart_at)} label="Departure from Coficab" />
                <DepotMarker left={pct(trip.return_at)} label="Return to Coficab" />
              </div>
            ))}
            {packed.map((delivery) => (
                <div
                  key={delivery.id}
                  className="absolute h-20"
                  style={{
                    left: `${Math.max(0, delivery._left)}%`,
                    top: `${12 + delivery._row * 94}px`,
                    width: `${Math.min(delivery._width, 100 - Math.max(0, delivery._left))}%`,
                    minWidth: 190,
                  }}
                >
                  <DeliveryBlock
                    delivery={delivery}
                    compact={delivery._width < 13}
                    minutesPerPixel={minutesPerPixel}
                    onResize={onResizeDelivery}
                    onCancel={onCancel}
                    onRestore={onRestore}
                  />
                </div>
              ))}
          </>
        )}
        {allStops.length === 0 && (
          <div className="absolute inset-0 flex items-center px-6 text-sm text-[#b0abb5]">idle</div>
        )}
      </div>
    </div>
  );
}
