import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Home,
  CalendarDays,
  FileText,
  Compass,
  Truck,
  Users,
  Settings,
  Cpu,
  Wand2,
  X,
} from 'lucide-react';

const mainNavItems = [
  { icon: Home, label: 'Dashboard', href: '/dashboard' },
  { icon: Cpu, label: 'AI Monitor', href: '/ai-monitor' },
  { icon: CalendarDays, label: 'Planning', href: '/planning' },
  { icon: FileText, label: 'Daily Planning', href: '/daily-planning' },
  { icon: Wand2, label: 'Generated Planning', href: '/generated-daily-planning' },
  { icon: Compass, label: 'Map', href: '/map' },
];

const fleetNavItems = [
  { icon: Users, label: 'Clients', href: '/clients' },
  { icon: Truck, label: 'Ressources', href: '/ressources' },
  { icon: Settings, label: 'Admin', href: '/admin' },
];

function NavLink({ icon: Icon, label, href, active, onNavigate }) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-label={label}
      aria-current={active ? 'page' : undefined}
      className={`group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
        active
          ? 'bg-white/15 text-white shadow-sm ring-1 ring-white/20'
          : 'text-white/80 hover:bg-white/10 hover:text-white'
      }`}
    >
      <span className="rounded-2xl bg-white/10 p-2 text-white transition-colors duration-200 group-hover:bg-white/20">
        <Icon size={18} />
      </span>
      {label}
    </Link>
  );
}

export default function Sidebar({ isOpen = false, onClose = () => {} }) {
  const pathname = usePathname();

  return (
    <>
      {/* Backdrop — mobile only, click to close. */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed left-0 top-0 z-50 h-screen w-72 transform bg-gradient-to-b from-brand-600 via-brand-700 to-brand-800 text-white shadow-2xl shadow-slate-900/25 transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="h-20 flex items-center gap-3 px-6 border-b border-white/10">
          <div className="w-12 h-12 rounded-3xl bg-white/15 flex items-center justify-center text-xl font-bold shadow-inner shadow-white/10">
            <span className="text-white">O</span>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-white/70">COFICAB</p>
            <p className="text-lg font-semibold">OptiRoute</p>
          </div>
          {/* Close button — mobile only. */}
          <button
            type="button"
            onClick={onClose}
            className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white hover:bg-white/20 lg:hidden"
            aria-label="Close navigation menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto h-[calc(100vh-180px)] px-5 py-6 space-y-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-white/70 mb-3">Main Menu</p>
            <div className="space-y-2">
              {mainNavItems.map((item) => (
                <NavLink
                  key={item.href}
                  icon={item.icon}
                  label={item.label}
                  href={item.href}
                  active={pathname === item.href}
                  onNavigate={onClose}
                />
              ))}
            </div>
          </div>

          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-white/70 mb-3">Fleet</p>
            <div className="space-y-2">
              {fleetNavItems.map((item) => (
                <NavLink
                  key={item.href}
                  icon={item.icon}
                  label={item.label}
                  href={item.href}
                  active={pathname === item.href}
                  onNavigate={onClose}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 px-5 py-5">
          <div className="flex items-center gap-3 rounded-3xl bg-white/10 p-3 backdrop-blur-sm">
            <div className="w-11 h-11 rounded-full bg-white/20 flex items-center justify-center text-sm font-semibold text-white shadow-sm shadow-white/10">
              GM
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold">Ghada Medimagh</p>
              <p className="text-xs text-white/70">Administrator</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
