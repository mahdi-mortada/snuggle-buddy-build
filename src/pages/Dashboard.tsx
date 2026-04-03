import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { StatCards } from '@/components/dashboard/StatCards';
import { LiveIncidentFeed, type LiveFeedItem } from '@/components/dashboard/LiveIncidentFeed';
import { RiskGauge } from '@/components/dashboard/RiskGauge';
import { TrendCharts } from '@/components/dashboard/TrendCharts';
import { RegionalRiskList } from '@/components/dashboard/RegionalRiskList';
import { useLiveData } from '@/hooks/useLiveData';
import { fetchBackendLiveIncidents, fetchBackendOfficialFeedPosts } from '@/services/backendApi';
import type { Incident, OfficialFeedPost } from '@/types/crisis';
import { RefreshCw, Download, Filter } from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

function toTimestamp(value: string): number {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) {
    return 0;
  }
  return timestamp;
}

export default function Dashboard() {
  const { incidents: dashboardIncidents, stats, alerts, riskScores, trendData, lastUpdated, updateCount, refresh, connectionStatus } = useLiveData(30000);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [officialFeeds, setOfficialFeeds] = useState<OfficialFeedPost[]>([]);
  const [mergedFeedLoading, setMergedFeedLoading] = useState(true);
  const [mergedFeedError, setMergedFeedError] = useState<string | null>(null);
  const isFetchingFeedRef = useRef(false);

  const loadMergedFeedSources = useCallback(async (showLoading = false) => {
    if (isFetchingFeedRef.current) {
      return;
    }

    isFetchingFeedRef.current = true;
    if (showLoading) {
      setMergedFeedLoading(true);
    }

    try {
      const [nextIncidents, nextOfficialFeeds] = await Promise.all([
        fetchBackendLiveIncidents(30),
        fetchBackendOfficialFeedPosts(24),
      ]);

      setIncidents(nextIncidents);
      setOfficialFeeds(nextOfficialFeeds);
      setMergedFeedError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load live feed data.';
      setMergedFeedError(message);
    } finally {
      if (showLoading) {
        setMergedFeedLoading(false);
      }
      isFetchingFeedRef.current = false;
    }
  }, []);

  useEffect(() => {
    void loadMergedFeedSources(true);
  }, [loadMergedFeedSources]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadMergedFeedSources(false);
    }, 10000);

    return () => {
      window.clearInterval(timer);
    };
  }, [loadMergedFeedSources]);

  const mergedFeed = useMemo<LiveFeedItem[]>(() => {
    const normalizedIncidents: LiveFeedItem[] = incidents.map((incident) => ({
      id: `incident-${incident.id}`,
      type: 'incident',
      title: incident.title,
      description: incident.description,
      timestamp: toTimestamp(incident.createdAt),
      source: incident.sourceInfo.name,
      incident,
    }));

    const normalizedTelegram: LiveFeedItem[] = officialFeeds.map((feed) => ({
      id: `telegram-${feed.id}`,
      type: 'telegram',
      title: feed.accountLabel || feed.publisherName,
      description: feed.content,
      timestamp: toTimestamp(feed.publishedAt),
      source: feed.publisherName,
      telegram: feed,
    }));

    return [...normalizedIncidents, ...normalizedTelegram].sort((left, right) => right.timestamp - left.timestamp);
  }, [incidents, officialFeeds]);

  const handleRetryMergedFeed = useCallback(() => {
    void loadMergedFeedSources(true);
  }, [loadMergedFeedSources]);

  return (
    <DashboardLayout liveData={{ incidents: dashboardIncidents, alerts, stats, lastUpdated, connectionStatus }}>
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
              onClick={() => { void refresh(true).then(() => toast.success('Data refreshed')); }}
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
            <LiveIncidentFeed
              items={mergedFeed}
              isLoading={mergedFeedLoading}
              error={mergedFeedError}
              onRetry={handleRetryMergedFeed}
            />
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
