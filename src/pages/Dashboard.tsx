import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { StatCards } from '@/components/dashboard/StatCards';
import { LiveIncidentFeed } from '@/components/dashboard/LiveIncidentFeed';
import { RiskGauge } from '@/components/dashboard/RiskGauge';
import { TrendCharts } from '@/components/dashboard/TrendCharts';
import { RegionalRiskList } from '@/components/dashboard/RegionalRiskList';
import { useLiveData } from '@/hooks/useLiveData';
import { RefreshCw, Download, Filter } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';

export default function Dashboard() {
  const { incidents, stats, riskScores, trendData, lastUpdated, updateCount, refresh } = useLiveData(30000);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Top bar with actions */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-foreground">Situation Overview</h1>
            <span className="text-[10px] text-muted-foreground font-mono-data bg-secondary/50 px-2 py-0.5 rounded">
              Updated: {format(lastUpdated, 'HH:mm:ss')}
            </span>
            {updateCount > 0 && (
              <span className="text-[10px] text-success font-mono-data animate-pulse">
                +{updateCount} updates
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { refresh(); toast.success('Data refreshed'); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh Now
            </button>
            <button
              onClick={() => toast.success('Report exported to PDF')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export
            </button>
            <button
              onClick={() => toast.info('Filter panel coming soon')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors"
            >
              <Filter className="w-3.5 h-3.5" />
              Filters
            </button>
          </div>
        </div>

        <StatCards stats={stats} />

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6" style={{ minHeight: '380px' }}>
          <div className="lg:col-span-3">
            <LiveIncidentFeed incidents={incidents} />
          </div>
          <div className="lg:col-span-2">
            <RiskGauge score={stats.avgRiskScore} trend={stats.riskTrend} />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6" style={{ minHeight: '400px' }}>
          <div className="lg:col-span-2">
            <TrendCharts data={trendData} />
          </div>
          <div>
            <RegionalRiskList riskScores={riskScores} />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
