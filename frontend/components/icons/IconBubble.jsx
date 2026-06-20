export default function IconBubble({ kind = 'default', size = 40 }) {
  const common = 'flex h-10 w-10 items-center justify-center rounded-full';
  const svgProps = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', xmlns: 'http://www.w3.org/2000/svg' };

  const icons = {
    box: (
      <svg {...svgProps}>
        <path d="M3 7.5L12 3l9 4.5v7L12 21 3 14.5v-7z" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    truck: (
      <svg {...svgProps}>
        <path d="M1 17h1.5a1.5 1.5 0 003 0H18a1 1 0 001-1v-5h-4V8h-7l-3 4v5z" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="7" cy="18" r="1.4" fill="white" />
        <circle cx="18" cy="18" r="1.4" fill="white" />
      </svg>
    ),
    user: (
      <svg {...svgProps}>
        <path d="M12 12a4 4 0 100-8 4 4 0 000 8z" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 20c1.5-3 4.5-4 8-4s6.5 1 8 4" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    clock: (
      <svg {...svgProps}>
        <circle cx="12" cy="12" r="9" stroke="white" strokeWidth="1.2" />
        <path d="M12 7v6l4 2" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    bolt: (
      <svg {...svgProps}>
        <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    chart: (
      <svg {...svgProps}>
        <path d="M3 3v18h18" stroke="white" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M7 13v5M12 8v10M17 11v7" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    default: (
      <svg {...svgProps}>
        <circle cx="12" cy="12" r="9" stroke="white" strokeWidth="1.2" />
      </svg>
    ),
  };

  const bg = kind === 'truck' || kind === 'bolt' ? 'bg-brand-600' : 'bg-[#6b7280]';

  return (
    <div className={`${common} ${bg}`} style={{ width: size, height: size }}>
      {icons[kind] || icons.default}
    </div>
  );
}
