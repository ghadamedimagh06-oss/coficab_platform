export default function StatCard({ title, value, hint, tone = 'text-brand', icon }) {
  return (
    <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.22em] text-slate-500">{title}</p>
          <p className={`mt-4 text-3xl font-semibold ${tone}`}>{value}</p>
        </div>
        {icon ? <div className="text-4xl">{icon}</div> : null}
      </div>
      {hint ? <p className="mt-4 text-sm text-slate-400">{hint}</p> : null}
    </div>
  );
}
