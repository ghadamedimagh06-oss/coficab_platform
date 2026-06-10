import { Truck } from 'lucide-react';
import { TICK_HOURS, pct } from './timeline';

// Left label column width — MUST stay in sync with TruckLane's grid template.
export const LANE_LABEL_CLASS = 'grid-cols-[16rem_1fr]';

export default function TimeAxis({ nowMinute = null }) {
  return (
    <div className={`sticky top-0 z-20 grid ${LANE_LABEL_CLASS} border-b border-[#ece8e1] bg-white/85 backdrop-blur`}>
      <div className="sticky left-0 z-30 flex items-center gap-2 border-r border-[#ece8e1] bg-white/90 px-5 py-3.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#7c3aed]/10 text-[#7c3aed]">
          <Truck size={16} />
        </span>
        <div className="leading-tight">
          <p className="text-[13px] font-semibold text-[#1a1a2e]">Fleet</p>
          <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-[#9e9aa4]">06:00 – 20:00</p>
        </div>
      </div>
      <div className="relative h-[52px]">
        {/* faint hour columns for rhythm */}
        {TICK_HOURS.slice(0, -1).map((hour, index) => (
          <div
            key={`band-${hour}`}
            className={index % 2 === 1 ? 'absolute top-0 h-full bg-[#faf9f6]' : 'absolute top-0 h-full'}
            style={{ left: `${(index / (TICK_HOURS.length - 1)) * 100}%`, width: `${100 / (TICK_HOURS.length - 1)}%` }}
          />
        ))}
        {TICK_HOURS.map((hour, index) => (
          <div
            key={hour}
            className="absolute top-0 flex h-full flex-col justify-center border-l border-[#ece8e1] pl-1.5"
            style={{ left: `${(index / (TICK_HOURS.length - 1)) * 100}%` }}
          >
            <span className="text-[11px] font-semibold tabular-nums text-[#6b6b7b]">
              {String(hour % 24).padStart(2, '0')}
              <span className="text-[#c4bfb6]">:00</span>
            </span>
          </div>
        ))}
        {nowMinute != null && (
          <div className="absolute top-0 z-20 h-full" style={{ left: `${pct(`${Math.floor(nowMinute / 60)}:${nowMinute % 60}`)}%` }}>
            <span className="absolute -top-0 left-0 -translate-x-1/2 rounded-full bg-[#7c3aed] px-1.5 py-0.5 text-[9px] font-bold text-white shadow-sm">
              NOW
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
