import { useState, useEffect, useCallback } from 'react';
import { mockIncidents, mockStats, mockRiskScores, mockAlerts, mockTrendData, allSources } from '@/data/mockData';
import type { Incident, DashboardStats, RiskScore, Alert, TrendDataPoint } from '@/types/crisis';

const sourceKeys = Object.keys(allSources) as (keyof typeof allSources)[];

function jitter(value: number, range: number) {
  return Math.round((value + (Math.random() - 0.5) * range) * 10) / 10;
}

function generateNewIncident(base: Incident[]): Incident {
  const template = base[Math.floor(Math.random() * base.length)];
  const srcKey = sourceKeys[Math.floor(Math.random() * sourceKeys.length)];
  const source = allSources[srcKey];
  const severities = ['low', 'medium', 'high', 'critical'] as const;
  const sev = severities[Math.floor(Math.random() * severities.length)];

  return {
    ...template,
    id: `live-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    source: srcKey,
    sourceInfo: source,
    severity: sev,
    riskScore: Math.floor(20 + Math.random() * 80),
    sentimentScore: Math.round((-0.5 + Math.random() * 0.8) * 100) / 100,
    createdAt: new Date().toISOString(),
    status: 'new',
    corroboratedBy: Math.random() > 0.5
      ? Array.from({ length: Math.floor(Math.random() * 3) + 1 }, () => allSources[sourceKeys[Math.floor(Math.random() * sourceKeys.length)]])
      : undefined,
  };
}

export function useLiveData(refreshInterval = 30000) {
  const [incidents, setIncidents] = useState<Incident[]>(mockIncidents);
  const [stats, setStats] = useState<DashboardStats>(mockStats);
  const [riskScores, setRiskScores] = useState<RiskScore[]>(mockRiskScores);
  const [alerts, setAlerts] = useState<Alert[]>(mockAlerts);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>(mockTrendData);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [updateCount, setUpdateCount] = useState(0);

  const refresh = useCallback(() => {
    // Add 1-2 new incidents at the top
    setIncidents((prev) => {
      const newOnes = Array.from({ length: Math.floor(Math.random() * 2) + 1 }, () => generateNewIncident(mockIncidents));
      return [...newOnes, ...prev].slice(0, 20);
    });

    // Update stats
    setStats((prev) => ({
      ...prev,
      totalIncidents24h: prev.totalIncidents24h + Math.floor(Math.random() * 5) + 1,
      activeAlerts: Math.max(5, Math.floor(jitter(prev.activeAlerts, 4))),
      avgRiskScore: Math.max(20, Math.min(95, jitter(prev.avgRiskScore, 8))),
      riskTrend: Math.round((Math.random() * 10 - 3) * 10) / 10,
    }));

    // Update risk scores
    setRiskScores((prev) =>
      prev.map((r) => ({
        ...r,
        overallScore: Math.max(15, Math.min(98, Math.round(jitter(r.overallScore, 6)))),
        confidence: Math.max(0.6, Math.min(0.99, jitter(r.confidence, 0.05))),
        calculatedAt: new Date().toISOString(),
      }))
    );

    // Add new trend data point
    setTrendData((prev) => {
      const last = prev[prev.length - 1];
      const newPoint: TrendDataPoint = {
        time: new Date().toISOString(),
        incidents: Math.floor(8 + Math.random() * 12),
        riskScore: Math.round(jitter(parseFloat(String(last.riskScore)), 10) * 10) / 10,
        sentiment: Math.round((-0.3 + Math.random() * 0.6) * 100) / 100,
      };
      return [...prev.slice(1), newPoint];
    });

    setLastUpdated(new Date());
    setUpdateCount((c) => c + 1);
  }, []);

  useEffect(() => {
    const timer = setInterval(refresh, refreshInterval);
    return () => clearInterval(timer);
  }, [refresh, refreshInterval]);

  return { incidents, stats, riskScores, alerts, trendData, lastUpdated, updateCount, refresh };
}
