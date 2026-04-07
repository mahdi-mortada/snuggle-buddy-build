import { Bell, Search, Wifi, WifiOff } from 'lucide-react';
import type { BackendConnectionStatus } from '@/hooks/useBackendWebSocket';

export function Header({
  connectionStatus = 'connected',
  unacknowledgedAlerts = 0,
}: {
  connectionStatus?: BackendConnectionStatus;
  unacknowledgedAlerts?: number;
}) {
  const connected = connectionStatus === 'connected';
  const connecting = connectionStatus === 'connecting';

  return (
    <header className="h-14 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-6">
      {/* Search */}
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-secondary/50 border border-border/50 w-full">
          <Search className="w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search incidents, regions, alerts..."
            className="bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none w-full"
          />
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Connection Status */}
        <div className="flex items-center gap-2 text-xs">
          {connected ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-success" />
              </span>
              <Wifi className="w-3.5 h-3.5 text-success" />
              <span className="text-muted-foreground hidden sm:inline">Live</span>
            </>
          ) : connecting ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-pulse relative inline-flex rounded-full h-2 w-2 bg-warning" />
              </span>
              <Wifi className="w-3.5 h-3.5 text-warning" />
              <span className="text-muted-foreground hidden sm:inline">Connecting</span>
            </>
          ) : (
            <>
              <span className="relative flex h-2 w-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-critical" />
              </span>
              <WifiOff className="w-3.5 h-3.5 text-critical" />
              <span className="text-muted-foreground hidden sm:inline">Disconnected</span>
            </>
          )}
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-accent transition-colors">
          <Bell className="w-5 h-5 text-muted-foreground" />
          {unacknowledgedAlerts > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-critical text-critical-foreground text-[9px] font-bold leading-none">
              {unacknowledgedAlerts > 99 ? '99+' : unacknowledgedAlerts}
            </span>
          )}
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-sm font-semibold text-primary">
            MM
          </div>
        </div>
      </div>
    </header>
  );
}
