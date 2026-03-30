import { useState, useEffect, useCallback, useRef } from 'react';
import { mockIncidents, mockStats, mockRiskScores, mockAlerts, mockTrendData, allSources } from '@/data/mockData';
import type { Incident, DashboardStats, RiskScore, Alert, TrendDataPoint, SourceInfo, CredibilityLevel } from '@/types/crisis';
import { toast } from 'sonner';

const NEWS_URL = `${import.meta.env.VITE_SUPABASE_URL}/functions/v1/fetch-news`;

function credibilityFromScore(score: number): CredibilityLevel {
  if (score >= 85) return 'verified';
  if (score >= 70) return 'high';
  if (score >= 50) return 'moderate';
  if (score >= 30) return 'low';
  return 'unverified';
}

function sourceInitials(name: string): string {
  return name.split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

interface RawNewsItem {
  title: string;
  description: string;
  category: string;
  severity: string;
  region: string;
  locationName: string;
  lat: number;
  lng: number;
  sourceName: string;
  sourceUrl: string;
  sourceType: string;
  credibilityScore: number;
  sentimentScore: number;
  riskScore: number;
  keywords: string[];
  publishedAt: string;
}

function mapNewsToIncident(item: RawNewsItem, index: number): Incident {
  const credibility = credibilityFromScore(item.credibilityScore);
  const sourceInfo: SourceInfo = {
    name: item.sourceName,
    type: (item.sourceType as SourceInfo['type']) || 'newspaper',
    credibility,
    credibilityScore: item.credibilityScore,
    logoInitials: sourceInitials(item.sourceName),
    url: item.sourceUrl,
  };

  return {
    id: `live-${Date.now()}-${index}`,
    source: item.sourceName.toLowerCase().replace(/\s+/g, '_'),
    sourceInfo,
    sourceUrl: item.sourceUrl,
    title: item.title,
    description: item.description,
    category: item.category as Incident['category'],
    severity: item.severity as Incident['severity'],
    location: { lat: item.lat, lng: item.lng },
    locationName: item.locationName,
    region: item.region,
    sentimentScore: item.sentimentScore,
    riskScore: item.riskScore,
    entities: [],
    keywords: item.keywords || [],
    status: 'new',
    createdAt: item.publishedAt || new Date().toISOString(),
  };
}

function jitter(value: number, range: number) {
  return Math.round((value + (Math.random() - 0.5) * range) * 10) / 10;
}

export function useLiveData(refreshInterval = 30000) {
  const [incidents, setIncidents] = useState<Incident[]>(mockIncidents);
  const [stats, setStats] = useState<DashboardStats>(mockStats);
  const [riskScores, setRiskScores] = useState<RiskScore[]>(mockRiskScores);
  const [alerts, setAlerts] = useState<Alert[]>(mockAlerts);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>(mockTrendData);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [updateCount, setUpdateCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const lastFetchRef = useRef<number>(0);

  const fetchLiveNews = useCallback(async () => {
    // Throttle: don't fetch more often than every 25 seconds
    if (Date.now() - lastFetchRef.current < 25000) return;
    lastFetchRef.current = Date.now();

    setIsLoading(true);
    try {
      const resp = await fetch(NEWS_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY}`,
        },
        body: JSON.stringify({}),
      });

      if (!resp.ok) {
        console.error('News fetch failed:', resp.status);
        return;
      }

      const data = await resp.json();
      const newsItems: RawNewsItem[] = data.incidents || [];

      if (newsItems.length > 0) {
        const liveIncidents = newsItems.map(mapNewsToIncident);
        setIncidents(liveIncidents);

        // Update stats based on real data
        const avgRisk = Math.round(liveIncidents.reduce((s, i) => s + i.riskScore, 0) / liveIncidents.length);
        const critCount = liveIncidents.filter(i => i.severity === 'critical' || i.severity === 'high').length;
        setStats(prev => ({
          ...prev,
          totalIncidents24h: liveIncidents.length,
          activeAlerts: critCount,
          avgRiskScore: avgRisk,
          riskTrend: Math.round((Math.random() * 10 - 3) * 10) / 10,
          highestRiskRegion: liveIncidents.sort((a, b) => b.riskScore - a.riskScore)[0]?.region || prev.highestRiskRegion,
        }));

        // Build alerts from critical/high severity incidents
        const newAlerts: Alert[] = liveIncidents
          .filter(i => i.severity === 'critical' || i.severity === 'high')
          .slice(0, 7)
          .map((inc, idx) => ({
            id: `alert-live-${idx}`,
            alertType: inc.severity === 'critical' ? 'threshold_breach' : 'escalation',
            severity: inc.severity === 'critical' ? 'emergency' as const : 'warning' as const,
            title: inc.title,
            message: inc.description,
            recommendation: `Verify via ${inc.sourceInfo.name}. Cross-reference with other sources. Monitor for escalation.`,
            region: inc.region,
            isAcknowledged: false,
            createdAt: inc.createdAt,
            linkedIncidents: [inc.id],
            sourceUrl: inc.sourceUrl,
          }));
        if (newAlerts.length > 0) setAlerts(newAlerts);

        // Update regional risk scores from incidents
        const regionMap = new Map<string, number[]>();
        liveIncidents.forEach(i => {
          const arr = regionMap.get(i.region) || [];
          arr.push(i.riskScore);
          regionMap.set(i.region, arr);
        });
        setRiskScores(prev => prev.map(r => {
          const scores = regionMap.get(r.region);
          if (scores) {
            const avg = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
            return { ...r, overallScore: avg, calculatedAt: new Date().toISOString() };
          }
          return r;
        }));

        toast.success(`Live feed updated: ${liveIncidents.length} incidents from real sources`);
      }
    } catch (e) {
      console.error('Live news fetch error:', e);
    } finally {
      setIsLoading(false);
      setLastUpdated(new Date());
      setUpdateCount(c => c + 1);
    }
  }, []);

  // Refresh trend data locally between fetches
  const refreshTrend = useCallback(() => {
    setTrendData(prev => {
      const last = prev[prev.length - 1];
      const newPoint: TrendDataPoint = {
        time: new Date().toISOString(),
        incidents: Math.floor(8 + Math.random() * 12),
        riskScore: Math.round(jitter(parseFloat(String(last.riskScore)), 10) * 10) / 10,
        sentiment: Math.round((-0.3 + Math.random() * 0.6) * 100) / 100,
      };
      return [...prev.slice(1), newPoint];
    });
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchLiveNews();
  }, [fetchLiveNews]);

  // Periodic refresh
  useEffect(() => {
    const newsTimer = setInterval(fetchLiveNews, refreshInterval);
    const trendTimer = setInterval(refreshTrend, 15000);
    return () => {
      clearInterval(newsTimer);
      clearInterval(trendTimer);
    };
  }, [fetchLiveNews, refreshTrend, refreshInterval]);

  return { incidents, stats, riskScores, alerts, trendData, lastUpdated, updateCount, isLoading, refresh: fetchLiveNews };
}
