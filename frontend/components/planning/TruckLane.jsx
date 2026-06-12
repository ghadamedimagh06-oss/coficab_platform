import { useCallback, useEffect, useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { Truck, Warehouse } from 'lucide-react';
import DeliveryBlock from './DeliveryBlock';
import DepotMarker from './DepotMarker';
import { LANE_LABEL_CLASS } from './TimeAxis';
import { WORK_START, WORK_END, toMinutes as minutes, pctIn } from './timeline';
import { palette } from '@/lib/theme';

function deliveryBox(delivery, spanMin) {
  const start = minutes(delivery.etd);
  const end = Math.max(minutes(delivery.eta), start + 30);
  const duration = Math.max(30, end - start);
  return {
    ...delivery,
    _start: start,
    _end: end,
    _left: ((start - WORK_START) / spanMin) * 100,
    _width: Math.max((duration / spanMin) * 100, 6),
  };
}

// Row packing reserves each card's *rendered* width (minBlockMinutes, derived
// from the card's pixel min-width), so two stops drop onto a second row only
// when their drawn boxes would truly overlap — never for a tiny clock gap, and
// never leaving boxes overlapping on one row.
function packedStops(stops, minBlockMinutes, spanMin) {
  const rows = [];
  return stops
    .map((s) => deliveryBox(s, spanMin))
    .sort((a, b) => a._start - b._start)
    .map((stop) => {
      const renderedEnd = Math.max(stop._end, stop._start + minBlockMinutes);
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
  if (ratio >= 0.7) return palette.brand[600];
  if (ratio >= 0.45) return '#f59e0b';
  return '#ef4444';
}

export default function TruckLane({ truck, markers = [], nowMinute = null, windowEnd = WORK_END, hosWarning = null, selected = false, onSelectTruck, onResizeDelivery, onCancel, onRestore, onDeleteMarker }) {
  const spanMin = Math.max(1, windowEnd - WORK_START);
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
  // Card min-width is 148px; reserve the same span (in minutes) for packing so
  // the row layout matches what's actually drawn.
  const MIN_BLOCK_PX = 132;
  const minBlockMinutes = laneWidth ? (MIN_BLOCK_PX / laneWidth) * spanMin : 55;
  const packed = packedStops(allStops, minBlockMinutes, spanMin);
  const truckMarkers = markers.filter((marker) => String(marker.truck_id) === String(truck.truck_id));
  const rowCount = Math.max(1, packed.reduce((max, stop) => Math.max(max, stop._row + 1), 1));
  const laneHeight = Math.max(allStops.length ? 124 : 84, rowCount * 104 + 24);
  const minutesPerPixel = laneWidth ? spanMin / laneWidth : 1;

  const capacityPositions = Number(truck.capacity_positions || 0);
  const usedPositions = allStops.reduce((sum, s) => sum + Number(s.quantity_positions || s.position_count || 0), 0);
  const tripCount = trips.length;
  const fillRatio = capacityPositions && tripCount ? usedPositions / (capacityPositions * tripCount) : 0;
  const isIdle = allStops.length === 0;
  const accent = isIdle ? '#c4bfb6' : fillColor(fillRatio);
  const nowLeft = nowMinute != null ? pctIn(`${Math.floor(nowMinute / 60)}:${nowMinute % 60}`, windowEnd) : null;

  // Each trip is bookended by COFICAB markers — the departure (its ETD) and the
  // return — with dashed "in transit" connectors showing the truck driving
  // between consecutive stops (gaps are travel, not idle). The return marker is
  // anchored just past the last card's drawn edge so it never sits inside it.
  const byId = new Map(packed.map((s) => [String(s.id), s]));
  const minWidthPct = laneWidth ? (MIN_BLOCK_PX / laneWidth) * 100 : 8;
  const connectors = [];
  const depots = [];
  const renderedRight = (s) => Math.max(0, s._left) + Math.max(s._width, minWidthPct);
  trips.forEach((trip, ti) => {
    const ts = tripStops[ti];
    if (!ts.length) return;
    const first = byId.get(String(ts[0].id));
    const last = byId.get(String(ts[ts.length - 1].id));

    // COFICAB departure (the trip's ETD) → drive to the first stop
    if (first) {
      const depotLeft = pctIn(trip.depart_at, windowEnd);
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
      const aRight = renderedRight(a);
      const bLeft = Math.max(0, b._left);
      if (bLeft - aRight > 1) {
        connectors.push({ key: `${a.id}-${b.id}`, left: aRight, width: bLeft - aRight, row: b._row, travel: b.travel_min });
      }
    }

    // last stop → drive back to COFICAB (the return), anchored after the card
    if (last && trip.return_at) {
      const lastRight = renderedRight(last);
      const retPos = Math.max(pctIn(trip.return_at, windowEnd), lastRight);
      depots.push({ key: `ret-${trip.trip_id}`, type: 'return', left: retPos, row: last._row, time: trip.return_at });
      if (retPos - lastRight > 1) {
        const homeMin = minutes(trip.return_at) - minutes(last.eta);
        connectors.push({ key: `cret-${trip.trip_id}`, left: lastRight, width: retPos - lastRight, row: last._row, travel: homeMin > 0 ? homeMin : null });
      }
    }
  });

  return (
    <div className={`grid ${LANE_LABEL_CLASS} border-b border-[#ece8e1] last:border-b-0`} style={{ minHeight: laneHeight }}>
      {/* Sticky truck card */}
      <div className={`sticky left-0 z-20 flex flex-col justify-center gap-2 border-r border-[#ece8e1] px-5 py-3 transition-colors ${selected ? 'bg-brand-600/5 ring-2 ring-inset ring-brand-600' : isIdle ? 'bg-[#fbfaf8]' : 'bg-white'}`}>
        <button
          type="button"
          onClick={() => onSelectTruck?.(truck.truck_id)}
          title={selected ? 'Hide this truck on the map' : 'Show this truck’s route on the map'}
          className="flex items-center gap-2.5 rounded-lg text-left transition hover:opacity-80"
        >
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white shadow-sm"
            style={{ backgroundColor: accent }}
          >
            <Truck size={16} />
          </span>
          <div className="min-w-0">
            <p className="flex items-center gap-1 truncate text-sm font-semibold text-ink">
              <span className="truncate">{truck.truck_label}</span>
              {hosWarning && (
                <span
                  className="shrink-0 text-[#d97706]"
                  title={`HOS: ${hosWarning.driving_minutes}m driving / ${hosWarning.on_duty_minutes}m on-duty exceeds the 9h/13h limit`}
                >
                  ⚠
                </span>
              )}
            </p>
            <p className="text-[11px] text-[#9e9aa4]">
              {capacityPositions.toLocaleString()} pos · {Number(truck.capacity_kg || 0).toLocaleString()} kg
            </p>
          </div>
        </button>
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
        className={`relative transition-colors ${isOver ? 'bg-brand-50' : isIdle ? 'bg-[#fcfbf9]' : 'bg-white'}`}
        style={{
          // one faint vertical gridline per hour (06–20 → 14 columns)
          backgroundImage: 'linear-gradient(to right,#f1ede6 1px,transparent 1px)',
          backgroundSize: '7.142857% 100%',
        }}
      >
        {/* live "now" line — z-0 keeps it behind the delivery cards */}
        {nowLeft != null && (
          <div className="pointer-events-none absolute top-0 bottom-0 z-0 w-px bg-brand-600/40" style={{ left: `${nowLeft}%` }} />
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
                  transform: 'translate(0, -50%)',
                }}
                title={d.type === 'depart' ? `Leaves COFICAB at ${d.time}` : `Back at COFICAB at ${d.time}`}
              >
                <span
                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[9px] font-bold text-white shadow-sm"
                  style={{ backgroundColor: d.type === 'depart' ? palette.brand[600] : '#a39e96' }}
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
              <DepotMarker key={marker.id} marker={marker} left={pctIn(marker.time, windowEnd)} label={marker.label || 'Manual marker'} onDelete={onDeleteMarker} />
            ))}
            {packed.map((delivery) => (
              <div
                key={delivery.id}
                className="absolute h-[88px]"
                style={{
                  left: `${Math.max(0, delivery._left)}%`,
                  top: `${12 + delivery._row * 104}px`,
                  width: `${Math.min(delivery._width, 100 - Math.max(0, delivery._left))}%`,
                  minWidth: MIN_BLOCK_PX,
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
          <DepotMarker key={marker.id} marker={marker} left={pctIn(marker.time, windowEnd)} label={marker.label || 'Manual marker'} onDelete={onDeleteMarker} />
        ))}
        {isIdle && (
          <div className="absolute inset-0 flex items-center px-6 text-xs font-medium text-[#c4bfb6]">No deliveries assigned</div>
        )}
      </div>
    </div>
  );
}
