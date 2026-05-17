import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { emoji: '🏠', label: 'Dashboard', href: '/dashboard' },
  { emoji: '📅', label: 'Planning', href: '/planning' },
  { emoji: '📋', label: 'Daily Planning', href: '/daily-planning' },
  { emoji: '🧭', label: 'Map', href: '/map' },
  { emoji: '📈', label: 'Analytics', href: '/analytics' },
  { emoji: '👥', label: 'Clients', href: '/clients' },
  { emoji: '⚙️', label: 'Admin', href: '/admin' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-72 bg-[#7c3aed] text-white shadow-2xl shadow-slate-900/20">
      <div className="h-20 flex items-center gap-3 px-6 border-b border-white/10">
        <div className="w-12 h-12 rounded-3xl bg-white/15 flex items-center justify-center text-xl font-bold">C</div>
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-white/70">COFICAB</p>
          <p className="text-lg font-semibold">OptiRoute</p>
        </div>
      </div>

      <div className="overflow-y-auto h-[calc(100vh-180px)] px-4 py-6 space-y-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-white/70 mb-3">Main Menu</p>
          <div className="space-y-2">
            {navItems.slice(0, 5).map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
                    active ? 'bg-white/15 text-white shadow-sm' : 'text-white/80 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  <span className="text-base">{item.emoji}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-white/70 mb-3">Fleet</p>
          <div className="space-y-2">
            {navItems.slice(5).map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
                    active ? 'bg-white/15 text-white shadow-sm' : 'text-white/80 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  <span className="text-base">{item.emoji}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 px-4 py-5">
        <div className="flex items-center gap-3 rounded-3xl bg-white/10 p-3">
          <div className="w-11 h-11 rounded-full bg-white/20 flex items-center justify-center text-sm font-semibold">JD</div>
          <div className="min-w-0">
            <p className="text-sm font-semibold">John Doe</p>
            <p className="text-xs text-white/70">Administrator</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
