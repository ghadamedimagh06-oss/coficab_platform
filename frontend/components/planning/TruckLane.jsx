import { useCallback, useEffect, useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { Truck, Warehouse } from 'lucide-react';
import DeliveryBlock from './DeliveryBlock';
import DepotMarker from './DepotMarker';
import { LANE_LABEL_CLASS } from './TimeAxis';
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

// Consecutive drops at the SAME site (e.g. a delivery split into parts that the
// same truck unloads back-to-back, zero drive between them) are merged into one
// block: combined positions/weight and the full time span. Without this they
// overlap and get bumped onto separate rows, looking like duplicates.
function mergeSameLocation(stops) {
  // Base customer ignoring an auto-split "(Site)" suffix, so split parts of one
  // customer merge but two genuinely different customers never do.
  const baseName = (x) => String(x.original_client || x.client || '').trim().toLowerCase();
  const out = [];
  stops.forEach((s) => {
    const prev = out[out.length - 1];
    const sameSite = prev
      && baseName(prev) === baseName(s)
      && Number(s.travel_min || 0) <= 1;
    if (sameSite) {
      out[out.length - 1] = {
        ...prev,
        eta: s.eta,
        quantity_positions: Number(prev.quantity_positions || prev.position_count || 0) + Number(s.quantity_positions || s.position_count || 0),
        position_count: Number(prev.position_count || prev.quantity_positions || 0) + Number(s.position_count || s.quantity_positions || 0),
        quantity_kg: Number(prev.quantity_kg || 0) + Number(s.quantity_kg || 0),
        _parts: (prev._parts || 1) + 1,
      };
    } else {
      out.push({ ...s });
    }
  });
  return out;
}

function fillColor(ratio) {
  if (ratio >= 0.9) return '#22c55e';
  if (ratio >= 0.7) return '#7c3aed';
  if (ratio >= 0.45) return '#f59e0b';
  return '#ef4444';
}

export default function TruckLane({ truck, markers = [], nowMinute = null, onResizeDelivery, onCancel, onRestore, onDeleteMarker }) {
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
  const tripStops = trips.map((trip) => mergeSameLocation(trip.stops || []));
  const allStops = tripStops.flat();
  const packed = packedStops(allStops);
  const truckMarkers = markers.filter((marker) => String(marker.truck_id) === String(truck.truck_id));
  const rowCount = Math.max(1, packed.reduce((max, stop) => Math.max(max, stop._row + 1), 1));
  const laneHeight = Math.max(allStops.length ? 124 : 84, rowCount * 104 + 24);
  const minutesPerPixel = laneWidth ? WORK_MINUTES / laneWidth : 1;

  const capacityPositions = Number(truck.capacity_positions || 0);
  const usedPositions = allStops.reduce((sum, s) => sum + Number(s.quantity_positions || s.position_count || 0), 0);
  const tripCount = trips.length;
  const fillRatio = capacityPositions && tripCount ? usedPositions / (capacityPositions * tripCount) : 0;
  const isIdle = allStops.length === 0;
  const accent = isIdle ? '#c4bfb6' : fillColor(fillRatio);
  const nowLeft = nowMinute != null ? pct(`${Math.floor(nowMinute / 60)}:${nowMinute % 60}`) : null;

  // Each trip starts with a COFICAB departure marker (its ETD), then dashed
  // "in transit" connectors show the truck driving between consecutive stops
  // (the gaps are travel, not idle). We only mark the departure — a return
  // marker landed inside the last (min-width) block and read as a bogus second
  // departure, so it is intentionally omitted.
  const byId = new Map(packed.map((s) => [String(s.id), s]));
  const minWidthPct = laneWidth ? (148 / laneWidth) * 100 : 8;
  const connectors = [];
  const depots = [];
  trips.forEach((trip, ti) => {
    const ts = tripStops[ti];
    if (!ts.length) return;
    const first = byId.get(String(ts[0].id));

    // COFICAB departure (the trip's ETD) → drive to the first stop
    if (first) {
      const depotLeft = pct(trip.depart_at);
      const firstLeft = Math.max(0, first._left);
      depots.push({ key: `dep-${trip.trip_id}`, type: 'depart', left: depotLeft, row: first._row, time: trip.depart_at });
      if (firstLeft - depotLeft > 1) {
        connectors.push({ key: `cdep-${trip.trip_id}`, left: depotLeft, width: firstLeft - depotLeft, row: first._row, travel: first.travel_min });
      }
    }

    // drive between consecutive stops of the same trip
    for (let i = 1; i < ts.length; i += 1) {
      const a = byId.get(String(ts[i - 1].id));
      const b = byId.get(String(ts[i].id));
      if (!a || !b || a._row !== b._row) continue;
      const aRight = Math.max(0, a._left) + Math.max(a._width, minWidthPct);
      const bLeft = Math.max(0, b._left);
      if (bLeft - aRight > 1) {
        connectors.push({ key: `${a.id}-${b.id}`, left: aRight, width: bLeft - aRight, row: b._row, travel: b.travel_min });
      }
    }
  });

  return (
    <div className={`grid ${LANE_LABEL_CLASS} border-b border-[#ece8e1] last:border-b-0`} style={{ minHeight: laneHeight }}>
      {/* Sticky truck card */}
      <div className={`sticky left-0 z-20 flex flex-col justify-center gap-2 border-r border-[#ece8e1] px-5 py-3 ${isIdle ? 'bg-[#fbfaf8]' : 'bg-white'}`}>
        <div className="flex items-center gap-2.5">
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white shadow-sm"
            style={{ backgroundColor: accent }}
          >
            <Truck size={16} />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[#1a1a2e]">{truck.truck_label}</p>
            <p className="text-[11px] text-[#9e9aa4]">
              {capacityPositions.toLocaleString()} pos · {Number(truck.capacity_kg || 0).toLocaleString()} kg
            </p>
          </div>
        </div>
        {isIdle ? (
          <span className="inline-flex w-fit items-center rounded-full bg-[#f0eee9] px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#a39e96]">
            Idle
          </span>
        ) : (
          <div>
            <div className="mb-1 flex items-center justify-between text-[10px] font-medium text-[#9e9aa4]">
              <span>{usedPositions} pos · {tripCount} trip{tripCount > 1 ? 's' : ''}</span>
              <span className="tabular-nums font-semibold" style={{ color: accent }}>{Math.round(fillRatio * 100)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[#f0eee9]">
              <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, Math.round(fillRatio * 100))}%`, backgroundColor: accent }} />
            </div>
          </div>
        )}
      </div>

      {/* Timeline track */}
      <div
        ref={setTimelineRef}
        className={`relative transition-colors ${isOver ? 'bg-[#f5f3ff]' : isIdle ? 'bg-[#fcfbf9]' : 'bg-white'}`}
        style={{
          // one faint vertical gridline per hour (06–20 → 14 columns)
          backgroundImage: 'linear-gradient(to right,#f1ede6 1px,transparent 1px)',
          backgroundSize: '7.142857% 100%',
        }}
      >
        {/* live "now" line — z-0 keeps it behind the delivery cards */}
        {nowLeft != null && (
          <div className="pointer-events-none absolute top-0 bottom-0 z-0 w-px bg-[#7c3aed]/40" style={{ left: `${nowLeft}%` }} />
        )}

        {!isIdle && (
          <>
            {depots.map((d) => (
              <div
                key={d.key}
                className="pointer-events-none absolute z-[2] flex items-center"
                style={{
                  left: `${d.left}%`,
                  top: `${12 + d.row * 104 + 44}px`,
                  transform: d.type === 'return' ? 'translate(-100%, -50%)' : 'translate(0, -50%)',
                }}
                title={d.type === 'depart' ? `Leaves COFICAB at ${d.time}` : `Back at COFICAB at ${d.time}`}
              >
                <span
                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-bold text-white shadow-sm"
                  style={{ backgroundColor: d.type === 'depart' ? '#7c3aed' : '#a39e96' }}
                >
                  <Warehouse size={9} />
                  {d.time}
                </span>
              </div>
            ))}
            {connectors.map((c) => (
              <div
                key={c.key}
                className="pointer-events-none absolute z-0 flex items-center"
                style={{ left: `${c.left}%`, width: `${c.width}%`, top: `${12 + c.row * 104}px`, height: 88 }}
              >
                <div className="h-0 flex-1 border-t border-dashed border-[#d8d3ca]" />
                {c.width > 4 && c.travel != null && (
                  <span className="mx-1 inline-flex shrink-0 items-center gap-0.5 rounded-full bg-white px-1.5 py-0.5 text-[9px] font-semibold text-[#9e9aa4] shadow-sm ring-1 ring-[#ece8e1]">
                    <Truck size={9} /> {c.travel}′
                  </span>
                )}
                <div className="h-0 flex-1 border-t border-dashed border-[#d8d3ca]" />
              </div>
            ))}
            {truckMarkers.map((marker) => (
              <DepotMarker key={marker.id} marker={marker} left={pct(marker.time)} label={marker.label || 'Manual marker'} onDelete={onDeleteMarker} />
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
                  minutesPerPixel={minutesPerPixel}
                  onResize={onResizeDelivery}
                  onCancel={onCancel}
                  onRestore={onRestore}
                />
              </div>
            ))}
          </>
        )}
        {isIdle && truckMarkers.map((marker) => (
          <DepotMarker key={marker.id} marker={marker} left={pct(marker.time)} label={marker.label || 'Manual marker'} onDelete={onDeleteMarker} />
        ))}
        {isIdle && (
          <div className="absolute inset-0 flex items-center px-6 text-xs font-medium text-[#c4bfb6]">No deliveries assigned</div>
        )}
      </div>
    </div>
  );
}
