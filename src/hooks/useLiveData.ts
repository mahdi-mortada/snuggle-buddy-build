import { useState, useEffect, useCallback, useRef } from 'react';
import { mockIncidents, mockStats, mockRiskScores, mockAlerts, mockTrendData } from '@/data/mockData';
import type { Incident, DashboardStats, RiskScore, Alert, TrendDataPoint, SourceInfo, CredibilityLevel } from '@/types/crisis';
import { useBackendWebSocket, type BackendConnectionStatus, type BackendWebSocketMessage } from '@/hooks/useBackendWebSocket';
import { runtimeConfig } from '@/lib/runtimeConfig';
import { acknowledgeBackendAlert, fetchBackendDashboardSnapshot } from '@/services/backendApi';
import { toast } from 'sonner';

const NEWS_URL = runtimeConfig.newsUrl;

const SEEN_SOURCE_URLS_KEY = "crisisshield.seenSourceUrls.v1";
const SEEN_TITLES_KEY = "crisisshield.seenTitles.v1";

function hashString(input: string): string {
  // Simple deterministic hash for stable IDs (not crypto).
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0; // keep 32-bit
  }
  return Math.abs(hash).toString(16);
}

function loadSeenSourceUrls(): Set<string> {
  try {
    if (typeof window === "undefined") return new Set();
    const raw = localStorage.getItem(SEEN_SOURCE_URLS_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((x) => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function loadSeenTitles(): string[] {
  try {
    if (typeof window === "undefined") return [];
    const raw = localStorage.getItem(SEEN_TITLES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x) => typeof x === "string" && x.trim().length > 0).slice(-250);
  } catch {
    return [];
  }
}

function persistSeenTitles(titles: string[]) {
  try {
    if (typeof window === "undefined") return;
    localStorage.setItem(SEEN_TITLES_KEY, JSON.stringify(titles.slice(-250)));
  } catch {
    // ignore storage failures
  }
}

function tokenizeTitle(title: string): string[] {
  // Keep Arabic + English alphanumerics; split into word tokens.
  return title
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function cosineSimilarityFromTitles(a: string, b: string): number {
  const aTokens = tokenizeTitle(a);
  const bTokens = tokenizeTitle(b);

  // Avoid noisy similarity for very short titles.
  if (aTokens.length < 3 || bTokens.length < 3) {
    return a.trim().toLowerCase() === b.trim().toLowerCase() ? 1 : 0;
  }

  const freqA = new Map<string, number>();
  const freqB = new Map<string, number>();
  for (const t of aTokens) freqA.set(t, (freqA.get(t) || 0) + 1);
  for (const t of bTokens) freqB.set(t, (freqB.get(t) || 0) + 1);

  let dot = 0;
  for (const [t, countA] of freqA.entries()) {
    const countB = freqB.get(t) || 0;
    dot += countA * countB;
  }

  let normA = 0;
  for (const countA of freqA.values()) normA += countA * countA;
  let normB = 0;
  for (const countB of freqB.values()) normB += countB * countB;

  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

function persistSeenSourceUrls(set: Set<string>) {
  try {
    if (typeof window === "undefined") return;
    localStorage.setItem(SEEN_SOURCE_URLS_KEY, JSON.stringify(Array.from(set).slice(-500)));
  } catch {
    // ignore storage failures (private mode, etc.)
  }
}

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

function incidentIdFromRaw(item: RawNewsItem, index: number): string {
  const seed = item.sourceUrl
    ? `sourceUrl:${item.sourceUrl}`
    : `fallback:${item.title}|${item.publishedAt}|${item.lat},${item.lng}|${item.region}|${index}`;
  return `inc-${hashString(seed)}`;
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
    id: incidentIdFromRaw(item, index),
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
  const incidentsRef = useRef<Incident[]>(mockIncidents);
  const [stats, setStats] = useState<DashboardStats>(mockStats);
  const [riskScores, setRiskScores] = useState<RiskScore[]>(mockRiskScores);
  const [alerts, setAlerts] = useState<Alert[]>(mockAlerts);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>(mockTrendData);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [updateCount, setUpdateCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const prevAvgRiskRef = useRef<number | null>(null);
  const hasShownLocalModeToastRef = useRef(false);
  const hasShownLiveFeedToastRef = useRef(false);
  const lastFetchRef = useRef<number>(0);
  const backendSyncTimerRef = useRef<number | null>(null);
  const seenSourceUrlsRef = useRef<Set<string>>(loadSeenSourceUrls());
  const seenTitlesRef = useRef<string[]>(loadSeenTitles());

  const applySnapshot = useCallback((snapshot: {
    incidents: Incident[];
    stats: DashboardStats;
    riskScores: RiskScore[];
    alerts: Alert[];
    trendData: TrendDataPoint[];
  }) => {
    const previousIds = new Set(incidentsRef.current.map((incident) => incident.id));
    const freshIds = snapshot.incidents.filter((incident) => !previousIds.has(incident.id)).length;

    incidentsRef.current = snapshot.incidents;
    setIncidents(snapshot.incidents);
    setStats(snapshot.stats);
    setRiskScores(snapshot.riskScores);
    setAlerts(snapshot.alerts);
    setTrendData(snapshot.trendData);
    setLastUpdated(new Date());
    setUpdateCount((count) => count + Math.max(freshIds, 1));
  }, []);

  const fetchBackendData = useCallback(async () => {
    const snapshot = await fetchBackendDashboardSnapshot();
    applySnapshot(snapshot);
  }, [applySnapshot]);

  const scheduleBackendSync = useCallback((delayMs = 250) => {
    if (backendSyncTimerRef.current) {
      window.clearTimeout(backendSyncTimerRef.current);
    }
    backendSyncTimerRef.current = window.setTimeout(() => {
      void fetchBackendData().catch((error) => {
        console.error('Backend websocket sync failed:', error);
      });
    }, delayMs);
  }, [fetchBackendData]);

  const fetchSupabaseNews = useCallback(async () => {
    // Throttle: don't fetch more often than every 25 seconds
    setIsLoading(true);
    try {
      const resp = await fetch(NEWS_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${runtimeConfig.supabasePublishableKey}`,
        },
        body: JSON.stringify({
          // Helps backend avoid duplicates when possible; client-side dedupe still applies.
          seenSourceUrls: Array.from(seenSourceUrlsRef.current).slice(-40),
          seenTitles: seenTitlesRef.current.slice(-30),
        }),
      });

      if (!resp.ok) {
        console.error('News fetch failed:', resp.status);
        return;
      }

      const data = await resp.json();
      const newsItems: RawNewsItem[] = data.incidents || [];

      if (newsItems.length > 0) {
        const fetchedIncidents = newsItems.map(mapNewsToIncident);

        // Deduplicate by title similarity (blueprint requirement: cosine similarity > 0.85).
        const acceptedIncidents: Incident[] = [];
        const acceptedTitles: string[] = [];
        const titleDupThreshold = 0.85;

        for (const inc of fetchedIncidents) {
          const title = inc.title || "";
          if (!title) continue;

          const dupInThisFetch = acceptedTitles.some((t) => cosineSimilarityFromTitles(t, title) > titleDupThreshold);
          const dupInSeenHistory = seenTitlesRef.current.some((t) => cosineSimilarityFromTitles(t, title) > titleDupThreshold);

          if (dupInThisFetch || dupInSeenHistory) continue;

          acceptedIncidents.push(inc);
          acceptedTitles.push(title);
        }

        // Persist seen URLs + titles to reduce duplicate news over time.
        acceptedIncidents.forEach((inc) => {
          if (inc.sourceUrl) seenSourceUrlsRef.current.add(inc.sourceUrl);
          if (inc.title) seenTitlesRef.current.push(inc.title);
        });
        persistSeenSourceUrls(seenSourceUrlsRef.current);
        persistSeenTitles(seenTitlesRef.current);
        // Keep the in-memory list bounded to avoid O(n^2) growth.
        if (seenTitlesRef.current.length > 250) {
          seenTitlesRef.current = seenTitlesRef.current.slice(-250);
        }

        // Keep a rolling deduped incident set (stable IDs prevent repeats).
        const byId = new Map<string, Incident>(incidentsRef.current.map((i) => [i.id, i]));
        acceptedIncidents.forEach((inc) => byId.set(inc.id, inc));
        const mergedIncidents = Array.from(byId.values())
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
          .slice(0, 30);
        incidentsRef.current = mergedIncidents;
        setIncidents(mergedIncidents);

        // Use "last 24h" slice for stats/alerts so older items don't skew.
        const cutoff24h = Date.now() - 24 * 3600 * 1000;
        const incidentsLast24h = mergedIncidents.filter((i) => {
          const t = new Date(i.createdAt).getTime();
          return Number.isFinite(t) && t >= cutoff24h;
        });
        const baseIncidents = incidentsLast24h.length > 0 ? incidentsLast24h : mergedIncidents;

        // Update stats based on real data
        const avgRisk = Math.round(baseIncidents.reduce((s, i) => s + i.riskScore, 0) / baseIncidents.length);
        const critCount = baseIncidents.filter((i) => i.severity === 'critical' || i.severity === 'high').length;
        const topRiskIncident = [...baseIncidents].sort((a, b) => b.riskScore - a.riskScore)[0];

        setStats(prev => ({
          ...prev,
          totalIncidents24h: baseIncidents.length,
          activeAlerts: critCount,
          avgRiskScore: avgRisk,
          riskTrend: prevAvgRiskRef.current !== null ? Math.round((avgRisk - prevAvgRiskRef.current) * 10) / 10 : 0,
          highestRiskRegion: topRiskIncident?.region || prev.highestRiskRegion,
        }));
        prevAvgRiskRef.current = avgRisk;

        // Build alerts from critical/high severity incidents
        const criticalIncidents = [...baseIncidents]
          .filter((i) => i.severity === 'critical' || i.severity === 'high')
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
          .slice(0, 7);

        const newAlerts: Alert[] = criticalIncidents.map((inc) => {
          const alertType = inc.severity === 'critical' ? 'threshold_breach' : 'escalation';
          const severity = inc.severity === 'critical' ? ('emergency' as const) : ('warning' as const);
          return {
            id: `alert-${inc.id}-${alertType}`,
            alertType,
            severity,
            title: inc.title,
            message: inc.description,
            recommendation: `Verify via ${inc.sourceInfo.name}. Cross-reference with other sources. Monitor for escalation.`,
            region: inc.region,
            isAcknowledged: false,
            createdAt: inc.createdAt,
            linkedIncidents: [inc.id],
          };
        });

        setAlerts(newAlerts);

        // Update regional risk scores from incidents
        const regionMap = new Map<string, number[]>();
        baseIncidents.forEach((i) => {
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

        toast.success(`Live feed updated: ${acceptedIncidents.length} new unique incidents`);
      }
    } catch (e) {
      console.error('Live news fetch error:', e);
    } finally {
      setIsLoading(false);
      setLastUpdated(new Date());
      setUpdateCount(c => c + 1);
    }
  }, []);

  const refresh = useCallback(async (force = false) => {
    if (!force && Date.now() - lastFetchRef.current < 25000) return;
    lastFetchRef.current = Date.now();

    if (!runtimeConfig.hasBackendApi && !runtimeConfig.hasSupabaseConfig) {
      setLastUpdated(new Date());
      return;
    }

    setIsLoading(true);
    try {
      if (runtimeConfig.hasBackendApi) {
        await fetchBackendData();
        return;
      }

      if (runtimeConfig.hasSupabaseConfig) {
        await fetchSupabaseNews();
      }
    } catch (error) {
      console.error('Live data refresh failed:', error);
      toast.error(error instanceof Error ? error.message : 'Unable to refresh live data.');
    } finally {
      setIsLoading(false);
      setLastUpdated(new Date());
    }
  }, [fetchBackendData, fetchSupabaseNews]);

  const acknowledgeAlert = useCallback(async (alertId: string) => {
    if (runtimeConfig.hasBackendApi) {
      const updated = await acknowledgeBackendAlert(alertId);
      setAlerts((current) => current.map((alert) => (alert.id === alertId ? updated : alert)));
      setStats((current) => ({
        ...current,
        activeAlerts: Math.max(0, current.activeAlerts - 1),
      }));
      return updated;
    }

    setAlerts((current) => current.map((alert) => (
      alert.id === alertId ? { ...alert, isAcknowledged: true } : alert
    )));
    return null;
  }, []);

  const acknowledgeAllAlerts = useCallback(async () => {
    const pendingIds = alerts.filter((alert) => !alert.isAcknowledged).map((alert) => alert.id);
    if (pendingIds.length === 0) return;

    if (runtimeConfig.hasBackendApi) {
      await Promise.all(pendingIds.map((alertId) => acknowledgeBackendAlert(alertId)));
      setAlerts((current) => current.map((alert) => ({ ...alert, isAcknowledged: true })));
      setStats((current) => ({ ...current, activeAlerts: 0 }));
      return;
    }

    setAlerts((current) => current.map((alert) => ({ ...alert, isAcknowledged: true })));
  }, [alerts]);

  const handleBackendMessage = useCallback((message: BackendWebSocketMessage) => {
    if (message.type === 'heartbeat') {
      setLastUpdated(new Date());
      return;
    }

    if (message.type === 'snapshot') {
      scheduleBackendSync(0);
      return;
    }

    if (message.type === 'incident' || message.type === 'risk_update' || message.type === 'alert') {
      scheduleBackendSync(150);
    }
  }, [scheduleBackendSync]);

  const connectionStatus: BackendConnectionStatus = useBackendWebSocket({
    enabled: runtimeConfig.hasBackendApi && Boolean(runtimeConfig.backendWsUrl),
    url: runtimeConfig.backendWsUrl,
    onMessage: handleBackendMessage,
  });

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
    if (runtimeConfig.hasBackendApi && !hasShownLocalModeToastRef.current) {
      toast.success('Connected to the local CrisisShield backend.');
      hasShownLocalModeToastRef.current = true;
    } else if (!runtimeConfig.hasBackendApi && !runtimeConfig.hasSupabaseConfig && !hasShownLocalModeToastRef.current) {
      toast.info('Running in local demo mode with mock data. Start the backend or add Supabase env vars to enable live updates.');
      hasShownLocalModeToastRef.current = true;
    }
    void refresh(true);
  }, [refresh]);

  useEffect(() => {
    if (connectionStatus === 'connected' && !hasShownLiveFeedToastRef.current && runtimeConfig.hasBackendApi) {
      toast.success('Live feed connected.');
      hasShownLiveFeedToastRef.current = true;
    }
  }, [connectionStatus]);

  // Periodic refresh
  useEffect(() => {
    const newsTimer = setInterval(() => {
      void refresh();
    }, refreshInterval);
    const trendTimer = runtimeConfig.hasBackendApi
      ? null
      : setInterval(refreshTrend, 15000);
    return () => {
      clearInterval(newsTimer);
      if (trendTimer) clearInterval(trendTimer);
    };
  }, [refresh, refreshInterval, refreshTrend]);

  useEffect(() => {
    return () => {
      if (backendSyncTimerRef.current) {
        window.clearTimeout(backendSyncTimerRef.current);
      }
    };
  }, []);

  return {
    incidents,
    stats,
    riskScores,
    alerts,
    trendData,
    lastUpdated,
    updateCount,
    isLoading,
    refresh,
    acknowledgeAlert,
    acknowledgeAllAlerts,
    connectionStatus,
  };
}
