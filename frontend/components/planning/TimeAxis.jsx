const TICKS = Array.from({ length: 10 }, (_, i) => 8 + i);

export default function TimeAxis() {
  return (
    <div className="sticky top-0 z-20 grid grid-cols-[10rem_1fr] border-b border-[#e8e5df] bg-[#f8f7f3]">
      <div className="px-4 py-4 text-xs font-semibold uppercase tracking-[0.18em] text-[#6b6b7b]">Truck</div>
      <div className="relative h-12">
        {TICKS.map((hour, index) => (
          <div
            key={hour}
            className="absolute top-0 h-full border-l border-[#e8e5df] px-2 py-3 text-xs font-semibold text-[#6b6b7b]"
            style={{ left: `${(index / (TICKS.length - 1)) * 100}%` }}
          >
            {String(hour).padStart(2, '0')}
          </div>
        ))}
      </div>
    </div>
  );
}
