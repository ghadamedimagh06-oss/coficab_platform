const statusStyles = {
  scheduled: {
    bg: '#f5f3ff',
    border: '#7c3aed',
    text: '#7c3aed',
  },
  'in-transit': {
    bg: '#eff6ff',
    border: '#3b82f6',
    text: '#3b82f6',
  },
  completed: {
    bg: '#f0fdf4',
    border: '#22c55e',
    text: '#22c55e',
  },
  delayed: {
    bg: '#fef2f2',
    border: '#ef4444',
    text: '#ef4444',
  },
  optimized: {
    bg: '#eef2ff',
    border: '#7c3aed',
    text: '#3730a3',
  },
};

export default function StatusBadge({ status = 'scheduled', size = 'md' }) {
  const style = statusStyles[status] || statusStyles.scheduled;
  const padding = size === 'sm' ? 'px-2 py-1 text-[10px]' : 'px-3 py-1.5 text-xs';
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ${padding}`}
      style={{
        backgroundColor: style.bg,
        borderColor: style.border,
        color: style.text,
        borderWidth: 1,
        borderStyle: 'solid',
      }}
    >
      {status.replace('-', ' ')}
    </span>
  );
}
