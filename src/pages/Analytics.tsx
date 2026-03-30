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
  const { riskScores, trendData, incidents, alerts, stats, lastUpdated } = useLiveData(30000);

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

  const predictionData = useMemo(() => trendData.slice(-24).map((d, i) => ({
    time: format(new Date(d.time), 'HH:mm'),
    actual: d.riskScore,
    predicted: i > 12 ? d.riskScore + (Math.random() * 10 - 3) : undefined,
    upper: i > 12 ? d.riskScore + 15 : undefined,
    lower: i > 12 ? d.riskScore - 10 : undefined,
  })), [trendData]);

  const anomalies = [
    { id: 1, timestamp: '2026-03-30 08:15', region: 'Beirut', type: 'Volume Spike', score: -0.82, details: 'Incident volume 3.2x above baseline' },
    { id: 2, timestamp: '2026-03-30 06:42', region: 'North Lebanon', type: 'Sentiment Shift', score: -0.71, details: 'Rapid negative sentiment acceleration' },
    { id: 3, timestamp: '2026-03-29 22:10', region: 'Mount Lebanon', type: 'Behavior Anomaly', score: -0.65, details: 'Coordinated posting pattern detected' },
    { id: 4, timestamp: '2026-03-29 18:33', region: 'Bekaa', type: 'Keyword Surge', score: -0.58, details: 'Threat keyword frequency 2.8x above normal' },
  ];

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats, lastUpdated }}>
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
                {anomalies.map((a) => (
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
