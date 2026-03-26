import { AppSidebar } from './AppSidebar';
import { Header } from './Header';

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full overflow-hidden">
      <AppSidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-6 scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  );
}
