// Shared timeline window for the generated daily planning Gantt.
// The backend schedules real trips from 06:00 (early long-haul departures) to
// 20:00 (returns from far zones like Kairouan/Sfax), so the axis must span the
// same window or long trips get clipped.

export const WORK_START = 6 * 60;   // 06:00
export const WORK_END = 20 * 60;    // 20:00
export const WORK_MINUTES = WORK_END - WORK_START; // 840
export const SNAP_MINUTES = 15;

// Hour ticks shown on the axis (06,07,...,20).
export const TICK_HOURS = Array.from(
  { length: WORK_END / 60 - WORK_START / 60 + 1 },
  (_, i) => WORK_START / 60 + i,
);

export function toMinutes(value) {
  if (!value) return WORK_START;
  const [hours, minutes = 0] = String(value).split(':').map(Number);
  return hours * 60 + minutes;
}

export function toClock(totalMinutes) {
  const safe = Math.max(0, Math.min(totalMinutes, 23 * 60 + 59));
  return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`;
}

// Position (0-100%) of a clock value along the timeline.
export function pct(value) {
  return Math.max(0, Math.min(100, ((toMinutes(value) - WORK_START) / WORK_MINUTES) * 100));
}

export function clampMinute(value, min = WORK_START, max = WORK_END) {
  return Math.max(min, Math.min(max, value));
}
