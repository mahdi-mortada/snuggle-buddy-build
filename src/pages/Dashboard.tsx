import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { StatCards } from '@/components/dashboard/StatCards';
import { LiveIncidentFeed } from '@/components/dashboard/LiveIncidentFeed';
import { RiskGauge } from '@/components/dashboard/RiskGauge';
import { TrendCharts } from '@/components/dashboard/TrendCharts';
import { RegionalRiskList } from '@/components/dashboard/RegionalRiskList';

export default function Dashboard() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Stats */}
        <StatCards />

        {/* Middle row */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6" style={{ minHeight: '380px' }}>
          <div className="lg:col-span-3">
            <LiveIncidentFeed />
          </div>
          <div className="lg:col-span-2">
            <RiskGauge />
          </div>
        </div>

        {/* Bottom row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" style={{ minHeight: '400px' }}>
          <div className="lg:col-span-2">
            <TrendCharts />
          </div>
          <div>
            <RegionalRiskList />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
