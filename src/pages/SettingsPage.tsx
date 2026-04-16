import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useLiveData } from '@/hooks/useLiveData';

export default function SettingsPage() {
  const { incidents, alerts, stats, lastUpdated, connectionStatus, acknowledgeAlert } = useLiveData(30000);

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats, lastUpdated, connectionStatus, acknowledgeAlert }}>
      <div className="space-y-6 max-w-2xl">
        <h1 className="text-xl font-bold text-foreground">Settings</h1>

        <div className="glass-panel p-6 space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-foreground mb-4">Alert Thresholds</h3>
            <div className="space-y-3">
              {[
                { label: 'Info', value: 40, color: 'text-info' },
                { label: 'Warning', value: 60, color: 'text-warning' },
                { label: 'Critical', value: 80, color: 'text-critical' },
                { label: 'Emergency', value: 90, color: 'text-critical' },
              ].map((t) => (
                <div key={t.label} className="flex items-center justify-between">
                  <span className={`text-sm ${t.color} font-medium`}>{t.label}</span>
                  <span className="text-sm font-mono-data text-muted-foreground">Risk Score &gt; {t.value}</span>
                </div>
              ))}
            </div>
          </div>

          <hr className="border-border/50" />

          <div>
            <h3 className="text-sm font-semibold text-foreground mb-4">Notification Channels</h3>
            <div className="space-y-3">
              {['Dashboard (Real-time)', 'Email (Critical & Emergency)', 'SMS (Emergency Only)', 'Webhook Integration'].map((ch) => (
                <div key={ch} className="flex items-center justify-between">
                  <span className="text-sm text-foreground/80">{ch}</span>
                  <div className="w-9 h-5 rounded-full bg-primary/30 relative cursor-pointer">
                    <div className="absolute right-0.5 top-0.5 w-4 h-4 rounded-full bg-primary" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <hr className="border-border/50" />

          <div>
            <h3 className="text-sm font-semibold text-foreground mb-4">System Information</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Version</span><span className="font-mono-data text-foreground">1.0.0</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">API Status</span><span className="text-success font-medium">Connected</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">ML Pipeline</span><span className="text-success font-medium">Running</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Last Risk Calc</span><span className="font-mono-data text-foreground">2 min ago</span></div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
