import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import {
  Home,
  CalendarDays,
  FileText,
  Compass,
  Globe2,
  BarChart3,
  Truck,
  Users,
  Settings,
  ChevronDown,
  Cpu,
  Wand2,
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

function NavLink({ icon: Icon, label, href, active }) {
  return (
    <Link
      href={href}
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

export default function Sidebar() {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState({});

  const toggle = (label) => setExpanded((s) => ({ ...s, [label]: !s[label] }));

  return (
    <aside className="fixed left-0 top-0 z-50 h-screen w-72 bg-gradient-to-b from-[#7c3aed] via-[#6d28d9] to-[#5b21b6] text-white shadow-2xl shadow-slate-900/25">
      <div className="h-20 flex items-center gap-3 px-6 border-b border-white/10">
        <div className="w-12 h-12 rounded-3xl bg-white/15 flex items-center justify-center text-xl font-bold shadow-inner shadow-white/10">
          <span className="text-white">O</span>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-white/70">COFICAB</p>
          <p className="text-lg font-semibold">OptiRoute</p>
        </div>
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
              />
            ))}
          </div>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-white/70 mb-3">Fleet</p>
          <div className="space-y-2">
            {fleetNavItems.map((item) => (
              item.children ? (
                <div key={item.href}>
                  <button
                    type="button"
                    onClick={() => toggle(item.label)}
                    className={`group flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200 text-white/80 hover:bg-white/10 hover:text-white`}
                  >
                    <span className="rounded-2xl bg-white/10 p-2 text-white transition-colors duration-200 group-hover:bg-white/20">
                      <item.icon size={18} />
                    </span>
                    <span className="flex-1 text-left">{item.label}</span>
                    <span className="text-white/60">
                      <ChevronDown size={16} />
                    </span>
                  </button>

                  {expanded[item.label] && (
                    <div className="mt-2 space-y-1 pl-6">
                      {item.children.map((child) => (
                        <NavLink
                          key={child.href}
                          icon={child.icon}
                          label={child.label}
                          href={child.href}
                          active={pathname === child.href}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <NavLink
                  key={item.href}
                  icon={item.icon}
                  label={item.label}
                  href={item.href}
                  active={pathname === item.href}
                />
              )
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
  );
}
