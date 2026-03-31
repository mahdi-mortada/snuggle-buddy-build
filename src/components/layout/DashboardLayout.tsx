import { useMemo } from 'react';
import { AppSidebar } from './AppSidebar';
import { Header } from './Header';
import { CrisisChat } from '@/components/chat/CrisisChat';
import type { Alert, DashboardStats, Incident } from '@/types/crisis';
import type { BackendConnectionStatus } from '@/hooks/useBackendWebSocket';

type LiveDataContext = {
  incidents: Incident[];
  alerts: Alert[];
  stats: DashboardStats;
  lastUpdated: Date;
  connectionStatus?: BackendConnectionStatus;
};

export function DashboardLayout({
  children,
  liveData,
}: {
  children: React.ReactNode;
  liveData?: LiveDataContext;
}) {
  const unacknowledgedCount = useMemo(
    () => (liveData?.alerts ?? []).filter((a) => !a.isAcknowledged).length,
    [liveData?.alerts]
  );

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <AppSidebar unacknowledgedCount={unacknowledgedCount} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header connectionStatus={liveData?.connectionStatus} unacknowledgedAlerts={unacknowledgedCount} />
        <main className="flex-1 overflow-auto p-6 scrollbar-thin">
          {children}
        </main>
      </div>
      <CrisisChat
        incidents={liveData?.incidents}
        alerts={liveData?.alerts}
        stats={liveData?.stats}
        lastUpdated={liveData?.lastUpdated}
      />
    </div>
  );
}
