import { useCallback, useEffect, useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import DeliveryBlock from './DeliveryBlock';
import DepotMarker from './DepotMarker';
import { WORK_START, WORK_MINUTES, toMinutes as minutes, pct } from './timeline';

function deliveryBox(delivery) {
  const start = minutes(delivery.etd);
  const end = Math.max(minutes(delivery.eta), start + 30);
  const duration = Math.max(30, end - start);
  return {
    ...delivery,
    _start: start,
    _end: end,
    _left: ((start - WORK_START) / WORK_MINUTES) * 100,
    _width: Math.max((duration / WORK_MINUTES) * 100, 8),
  };
}

// A delivery block is rendered at least this wide (in timeline minutes) so its
// label stays readable. Row packing reserves this width too: a truck's stops are
// sequential, so two stops only drop onto a second row when their *rendered*
// boxes would physically overlap — never because of a tiny clock gap. This kills
// the old illusion of one truck running "parallel" deliveries.
const MIN_BLOCK_MINUTES = 55;

function packedStops(stops) {
  const rows = [];
  return stops
    .map(deliveryBox)
    .sort((a, b) => a._start - b._start)
    .map((stop) => {
      const renderedEnd = Math.max(stop._end, stop._start + MIN_BLOCK_MINUTES);
      let rowIndex = rows.findIndex((rowEnd) => stop._start >= rowEnd);
      if (rowIndex === -1) {
        rowIndex = rows.length;
        rows.push(renderedEnd);
      } else {
        rows[rowIndex] = renderedEnd;
      }
      return { ...stop, _row: rowIndex, _rowCount: rows.length };
    });
}

export default function TruckLane({ truck, markers = [], onResizeDelivery, onCancel, onRestore, onDeleteMarker }) {
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
  const truckMarkers = markers.filter((marker) => String(marker.truck_id) === String(truck.truck_id));
  const rowCount = Math.max(1, packed.reduce((max, stop) => Math.max(max, stop._row + 1), 1));
  const laneHeight = Math.max(124, rowCount * 104 + 24);
  const minutesPerPixel = laneWidth ? WORK_MINUTES / laneWidth : 1;

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
        // One vertical gridline per hour, aligned with the TimeAxis ticks
        // (06:00–20:00 → 14 columns). 100/14 ≈ 7.142857%.
        style={{ backgroundSize: '7.142857% 100%' }}
      >
        {allStops.length > 0 && (
          <>
            {truckMarkers.map((marker) => (
              <DepotMarker
                key={marker.id}
                marker={marker}
                left={pct(marker.time)}
                label={marker.label || 'Manual marker'}
                onDelete={onDeleteMarker}
              />
            ))}
            {packed.map((delivery) => (
                <div
                  key={delivery.id}
                  className="absolute h-[88px]"
                  style={{
                    left: `${Math.max(0, delivery._left)}%`,
                    top: `${12 + delivery._row * 104}px`,
                    width: `${Math.min(delivery._width, 100 - Math.max(0, delivery._left))}%`,
                    minWidth: 148,
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
        {allStops.length === 0 && truckMarkers.map((marker) => (
          <DepotMarker
            key={marker.id}
            marker={marker}
            left={pct(marker.time)}
            label={marker.label || 'Manual marker'}
            onDelete={onDeleteMarker}
          />
        ))}
        {allStops.length === 0 && (
          <div className="absolute inset-0 flex items-center px-6 text-sm text-[#b0abb5]">idle</div>
        )}
      </div>
    </div>
  );
}
