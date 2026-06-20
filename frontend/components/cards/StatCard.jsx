export default function StatCard({ title, value, hint, tone = 'text-brand-600', icon }) {
  return (
    <div className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.22em] text-muted">{title}</p>
          <p className={`mt-4 text-3xl font-semibold ${tone}`}>{value}</p>
        </div>
        {icon ? <div className="text-4xl">{icon}</div> : null}
      </div>
      {hint ? <p className="mt-4 text-sm text-muted">{hint}</p> : null}
    </div>
  );
}
