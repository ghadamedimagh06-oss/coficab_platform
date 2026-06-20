"use client";

export default function BarChart({ data = [], labelKey = 'label', valueKey = 'value', title }) {
  const max = Math.max(...data.map((item) => item[valueKey]), 1);
  return (
    <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
      <div className="mb-5 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink">{title}</h3>
      </div>
      <div className="space-y-4">
        {data.map((item, index) => (
          <div key={index}>
            <div className="flex items-center justify-between text-sm text-muted">
              <span>{item[labelKey]}</span>
              <span>{item[valueKey]}</span>
            </div>
            <div className="mt-2 h-3 w-full rounded-full bg-[#f0ede8]">
              <div
                className="h-3 rounded-full bg-brand-600"
                style={{ width: `${Math.max(4, (item[valueKey] / max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
