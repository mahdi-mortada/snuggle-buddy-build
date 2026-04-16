import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useLiveData } from '@/hooks/useLiveData';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  AreaChart, Area,
} from 'recharts';
import { format } from 'date-fns';
import { useMemo } from 'react';

const tooltipStyle = {
  contentStyle: { backgroundColor: 'hsl(222 47% 11%)', border: '1px solid hsl(215 28% 22%)', borderRadius: '8px', fontSize: '12px', color: '#e2e8f0' },
};

export default function Analytics() {
  const { riskScores, trendData, incidents, alerts, stats, lastUpdated, connectionStatus, acknowledgeAlert } = useLiveData(30000);

  const riskBreakdownData = useMemo(() => riskScores.map((r) => ({
    region: r.region.replace(' Lebanon', '').replace('Baalbek-Hermel', 'B-Hermel'),
    Sentiment: r.sentimentComponent,
    Volume: r.volumeComponent,
    Keyword: r.keywordComponent,
    Behavior: r.behaviorComponent,
    Geospatial: r.geospatialComponent,
  })), [riskScores]);

  const topRegion = useMemo(() => riskScores.reduce((a, b) => a.overallScore > b.overallScore ? a : b), [riskScores]);
  
  const radarData = useMemo(() => [
    { subject: 'Sentiment', value: topRegion.sentimentComponent },
    { subject: 'Volume', value: topRegion.volumeComponent },
    { subject: 'Keyword', value: topRegion.keywordComponent },
    { subject: 'Behavior', value: topRegion.behaviorComponent },
    { subject: 'Geospatial', value: topRegion.geospatialComponent },
  ], [topRegion]);

  const sentimentData = useMemo(() => trendData.slice(-72).map((d) => ({
    time: format(new Date(d.time), 'MMM dd HH:mm'),
    sentiment: d.sentiment,
  })), [trendData]);

  const predictionData = useMemo(() => {
    const slice = trendData.slice(-24);
    if (slice.length < 2) return slice.map((d) => ({
      time: format(new Date(d.time), 'HH:mm'),
      actual: d.riskScore,
      predicted: undefined,
      upper: undefined,
      lower: undefined,
    }));
    const lastActual = slice[slice.length - 1].riskScore;
    const slope = lastActual - slice[slice.length - 2].riskScore;
    return slice.map((d, i) => {
      const stepsAhead = i - 12;
      const isProjected = i > 12;
      const projected = isProjected ? Math.min(100, Math.max(0, lastActual + slope * stepsAhead)) : undefined;
      return {
        time: format(new Date(d.time), 'HH:mm'),
        actual: d.riskScore,
        predicted: isProjected ? Math.round(projected! * 10) / 10 : undefined,
        upper: isProjected ? Math.min(100, Math.round((projected! + 8) * 10) / 10) : undefined,
        lower: isProjected ? Math.max(0, Math.round((projected! - 8) * 10) / 10) : undefined,
      };
    });
  }, [trendData]);

  const anomalies = useMemo(() => {
    if (!incidents || incidents.length === 0) return [];
    const regionScores = new Map<string, number[]>();
    for (const inc of incidents) {
      const scores = regionScores.get(inc.region) ?? [];
      scores.push(inc.riskScore);
      regionScores.set(inc.region, scores);
    }
    const regionAvg = new Map<string, number>();
    for (const [region, scores] of regionScores.entries()) {
      regionAvg.set(region, scores.reduce((a, b) => a + b, 0) / scores.length);
    }
    const ANOMALY_THRESHOLD = 15;
    return incidents
      .filter((inc) => inc.riskScore - (regionAvg.get(inc.region) ?? 0) >= ANOMALY_THRESHOLD)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 10)
      .map((inc, i) => ({
        id: i + 1,
        timestamp: format(new Date(inc.createdAt), 'yyyy-MM-dd HH:mm'),
        region: inc.region,
        type: inc.category === 'cyber' ? 'Keyword Surge' : inc.severity === 'critical' ? 'Volume Spike' : 'Behavior Anomaly',
        score: Math.round((inc.riskScore / -100) * 100) / 100,
        details: `${inc.title} — Risk score ${inc.riskScore} vs. regional avg ${Math.round(regionAvg.get(inc.region) ?? 0)}`,
      }));
  }, [incidents]);

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats, lastUpdated, connectionStatus, acknowledgeAlert }}>
      <div className="space-y-6">
        <h1 className="text-xl font-bold text-foreground">Analytics & Intelligence</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 glass-panel p-4" style={{ height: '350px' }}>
            <h3 className="text-sm font-semibold text-foreground mb-3">Risk Score Breakdown by Region</h3>
            <ResponsiveContainer width="100%" height="90%">
              <BarChart data={riskBreakdownData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="region" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <Tooltip {...tooltipStyle} />
                <Bar dataKey="Sentiment" stackId="a" fill="hsl(var(--chart-4))" radius={[0, 0, 0, 0]} />
                <Bar dataKey="Volume" stackId="a" fill="hsl(var(--chart-3))" />
                <Bar dataKey="Keyword" stackId="a" fill="hsl(var(--chart-1))" />
                <Bar dataKey="Behavior" stackId="a" fill="hsl(var(--chart-5))" />
                <Bar dataKey="Geospatial" stackId="a" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="glass-panel p-4" style={{ height: '350px' }}>
            <h3 className="text-sm font-semibold text-foreground mb-1">Top Risk Region: {topRegion.region}</h3>
            <p className="text-[10px] text-muted-foreground mb-2">Component Analysis</p>
            <ResponsiveContainer width="100%" height="85%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="hsl(var(--border))" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <PolarRadiusAxis tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} domain={[0, 100]} />
                <Radar dataKey="value" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.2} strokeWidth={2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass-panel p-4" style={{ height: '300px' }}>
            <h3 className="text-sm font-semibold text-foreground mb-3">Sentiment Trend (72h)</h3>
            <ResponsiveContainer width="100%" height="85%">
              <AreaChart data={sentimentData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="time" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} interval="preserveStartEnd" />
                <YAxis domain={[-1, 1]} tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <Tooltip {...tooltipStyle} />
                <Area type="monotone" dataKey="sentiment" stroke="hsl(var(--chart-5))" fill="hsl(var(--chart-5))" fillOpacity={0.15} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="glass-panel p-4" style={{ height: '300px' }}>
            <h3 className="text-sm font-semibold text-foreground mb-3">Risk Prediction (24h Forecast)</h3>
            <ResponsiveContainer width="100%" height="85%">
              <LineChart data={predictionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
                <Tooltip {...tooltipStyle} />
                <Line type="monotone" dataKey="actual" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="predicted" stroke="hsl(var(--warning))" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                <Line type="monotone" dataKey="upper" stroke="hsl(var(--warning))" strokeWidth={1} strokeDasharray="2 2" dot={false} opacity={0.4} />
                <Line type="monotone" dataKey="lower" stroke="hsl(var(--warning))" strokeWidth={1} strokeDasharray="2 2" dot={false} opacity={0.4} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-panel p-4">
          <h3 className="text-sm font-semibold text-foreground mb-4">Anomaly Detection Log</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Timestamp</th>
                  <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Region</th>
                  <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Type</th>
                  <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Score</th>
                  <th className="text-left py-2 px-3 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 px-3 text-center text-xs text-muted-foreground">No anomalies detected in current data.</td>
                  </tr>
                ) : anomalies.map((a) => (
                  <tr key={a.id} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                    <td className="py-2.5 px-3 font-mono-data text-xs text-muted-foreground">{a.timestamp}</td>
                    <td className="py-2.5 px-3 text-xs text-foreground">{a.region}</td>
                    <td className="py-2.5 px-3">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-warning/15 text-warning border border-warning/30">{a.type}</span>
                    </td>
                    <td className="py-2.5 px-3 font-mono-data text-xs text-critical">{a.score}</td>
                    <td className="py-2.5 px-3 text-xs text-muted-foreground">{a.details}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
