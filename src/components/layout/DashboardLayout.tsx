import { AppSidebar } from './AppSidebar';
import { Header } from './Header';
import { CrisisChat } from '@/components/chat/CrisisChat';
import type { Alert, DashboardStats, Incident } from '@/types/crisis';

type LiveDataContext = {
  incidents: Incident[];
  alerts: Alert[];
  stats: DashboardStats;
  lastUpdated: Date;
};

export function DashboardLayout({
  children,
  liveData,
}: {
  children: React.ReactNode;
  liveData?: LiveDataContext;
}) {
  return (
    <div className="flex h-screen w-full overflow-hidden">
      <AppSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
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
