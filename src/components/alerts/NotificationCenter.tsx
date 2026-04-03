import { useState, useRef } from 'react';
import { Bell } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { Alert } from '@/types/crisis';

interface NotificationCenterProps {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
}

const severityDot: Record<Alert['severity'], string> = {
  emergency: 'bg-critical animate-pulse',
  critical: 'bg-critical',
  warning: 'bg-warning',
  info: 'bg-info',
};

export function NotificationCenter({ alerts, onAcknowledge }: NotificationCenterProps) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const unread = alerts.filter((a) => !a.isAcknowledged);
  const unreadCount = unread.length;

  // Show at most 20 most recent
  const displayAlerts = alerts
    .slice()
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 20);

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center w-8 h-8 rounded-lg hover:bg-accent transition-colors"
        aria-label="Notifications"
      >
        <Bell className="w-4 h-4 text-muted-foreground" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-0.5 rounded-full bg-critical text-[9px] font-bold text-white flex items-center justify-center leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Panel */}
          <div className="absolute right-0 top-10 z-50 w-80 glass-panel border border-border/60 shadow-xl rounded-lg overflow-hidden animate-fade-in-up">
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/50">
              <span className="text-xs font-semibold text-foreground">Notifications</span>
              {unreadCount > 0 && (
                <span className="text-[10px] text-muted-foreground font-mono-data">
                  {unreadCount} unread
                </span>
              )}
            </div>

            <div className="max-h-[360px] overflow-y-auto divide-y divide-border/30">
              {displayAlerts.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted-foreground">
                  No alerts yet.
                </div>
              ) : (
                displayAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className={`px-3 py-2.5 flex gap-2.5 items-start transition-colors hover:bg-accent/30 ${
                      alert.isAcknowledged ? 'opacity-50' : ''
                    }`}
                  >
                    <span
                      className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${severityDot[alert.severity]}`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground leading-snug line-clamp-2">
                        {alert.title}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[10px] text-muted-foreground">{alert.region}</span>
                        <span className="text-muted-foreground/30 text-[10px]">•</span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatDistanceToNow(new Date(alert.createdAt), { addSuffix: true })}
                        </span>
                      </div>
                    </div>
                    {!alert.isAcknowledged && (
                      <button
                        onClick={() => onAcknowledge(alert.id)}
                        className="text-[10px] text-primary hover:text-primary/70 shrink-0 mt-0.5 transition-colors"
                      >
                        ACK
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>

            {unreadCount > 0 && (
              <div className="border-t border-border/50 px-3 py-2">
                <button
                  onClick={() => {
                    unread.forEach((a) => onAcknowledge(a.id));
                    setOpen(false);
                  }}
                  className="w-full text-[10px] text-center text-primary hover:text-primary/70 transition-colors font-medium"
                >
                  Acknowledge all {unreadCount} alerts
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
