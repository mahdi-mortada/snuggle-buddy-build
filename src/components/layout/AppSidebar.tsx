import { useState } from 'react';
import { NavLink } from '@/components/NavLink';
import { useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Map,
  BarChart3,
  Bell,
  Settings,
  Shield,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const navItems = [
  { title: 'Dashboard', url: '/', icon: LayoutDashboard },
  { title: 'Incident Map', url: '/map', icon: Map },
  { title: 'Analytics', url: '/analytics', icon: BarChart3 },
  { title: 'Alerts', url: '/alerts', icon: Bell },
  { title: 'Settings', url: '/settings', icon: Settings },
];

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <aside
      className={`flex flex-col bg-sidebar border-r border-sidebar-border transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-sidebar-border">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/20">
          <Shield className="w-5 h-5 text-primary" />
        </div>
        {!collapsed && (
          <div className="flex flex-col">
            <span className="text-sm font-bold text-foreground tracking-tight">CrisisShield</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest">Security Operations</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.url;
          return (
            <NavLink
              key={item.url}
              to={item.url}
              end
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                isActive
                  ? ''
                  : 'text-sidebar-foreground hover:text-foreground hover:bg-sidebar-accent'
              }`}
              activeClassName="bg-primary/15 text-primary font-medium glow-primary"
            >
              <item.icon className="w-5 h-5 shrink-0" />
              {!collapsed && <span>{item.title}</span>}
              {!collapsed && item.url === '/alerts' && (
                <span className="ml-auto flex items-center justify-center w-5 h-5 rounded-full bg-critical text-critical-foreground text-[10px] font-bold">
                  5
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center h-12 border-t border-sidebar-border text-muted-foreground hover:text-foreground transition-colors"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
