export default function DepotMarker({ left, label }) {
  return (
    <div
      className="absolute top-0 z-10 h-full w-2 border border-red-300 bg-[repeating-linear-gradient(135deg,#ef4444_0,#ef4444_3px,#fee2e2_3px,#fee2e2_6px)]"
      style={{ left: `${left}%` }}
      title={label}
    />
  );
}
