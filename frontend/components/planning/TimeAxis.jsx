import { Truck } from 'lucide-react';
import { WORK_END, ticksTo, pctIn } from './timeline';

// Left label column width — MUST stay in sync with TruckLane's grid template.
export const LANE_LABEL_CLASS = 'grid-cols-[16rem_1fr]';

export default function TimeAxis({ nowMinute = null, windowEnd = WORK_END }) {
  const ticks = ticksTo(windowEnd);
  const span = Math.max(1, ticks.length - 1);
  const endLabel = `${String(Math.round(windowEnd / 60) % 24).padStart(2, '0')}:00`;

  return (
    <div className={`sticky top-0 z-20 grid ${LANE_LABEL_CLASS} border-b border-[#ece8e1] bg-white/85 backdrop-blur`}>
      <div className="sticky left-0 z-30 flex items-center gap-2 border-r border-[#ece8e1] bg-white/90 px-5 py-3.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600/10 text-brand-600">
          <Truck size={16} />
        </span>
        <div className="leading-tight">
          <p className="text-[13px] font-semibold text-ink">Fleet</p>
          <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-[#9e9aa4]">06:00 – {endLabel}</p>
        </div>
      </div>
      <div className="relative h-[52px]">
        {/* faint hour columns for rhythm */}
        {ticks.slice(0, -1).map((hour, index) => (
          <div
            key={`band-${hour}`}
            className={index % 2 === 1 ? 'absolute top-0 h-full bg-[#faf9f6]' : 'absolute top-0 h-full'}
            style={{ left: `${(index / span) * 100}%`, width: `${100 / span}%` }}
          />
        ))}
        {ticks.map((hour, index) => (
          <div
            key={hour}
            className="absolute top-0 flex h-full flex-col justify-center border-l border-[#ece8e1] pl-1.5"
            style={{ left: `${(index / span) * 100}%` }}
          >
            <span className="text-[11px] font-semibold tabular-nums text-muted">
              {String(hour % 24).padStart(2, '0')}
              <span className="text-[#c4bfb6]">:00</span>
            </span>
          </div>
        ))}
        {nowMinute != null && (
          <div className="absolute top-0 z-20 h-full" style={{ left: `${pctIn(`${Math.floor(nowMinute / 60)}:${nowMinute % 60}`, windowEnd)}%` }}>
            <span className="absolute -top-0 left-0 -translate-x-1/2 rounded-full bg-brand-600 px-1.5 py-0.5 text-[9px] font-bold text-white shadow-sm">
              NOW
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
