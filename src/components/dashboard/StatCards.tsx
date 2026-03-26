import { TrendingUp, TrendingDown, AlertTriangle, Activity, MapPin, Shield } from 'lucide-react';
import { mockStats } from '@/data/mockData';

const statCards = [
  {
    label: 'Total Incidents (24h)',
    value: mockStats.totalIncidents24h,
    icon: Activity,
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    borderColor: 'border-primary/20',
  },
  {
    label: 'Active Alerts',
    value: mockStats.activeAlerts,
    icon: AlertTriangle,
    color: 'text-critical',
    bgColor: 'bg-critical/10',
    borderColor: 'border-critical/20',
  },
  {
    label: 'Avg Risk Score',
    value: mockStats.avgRiskScore.toFixed(1),
    icon: Shield,
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    borderColor: 'border-warning/20',
    trend: mockStats.riskTrend,
  },
  {
    label: 'Highest Risk Region',
    value: mockStats.highestRiskRegion,
    icon: MapPin,
    color: 'text-critical',
    bgColor: 'bg-critical/10',
    borderColor: 'border-critical/20',
    subtitle: '78/100',
  },
];

export function StatCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {statCards.map((card) => (
        <div
          key={card.label}
          className={`glass-panel p-4 border ${card.borderColor} animate-fade-in-up`}
        >
          <div className="flex items-start justify-between mb-3">
            <div className={`p-2 rounded-lg ${card.bgColor}`}>
              <card.icon className={`w-5 h-5 ${card.color}`} />
            </div>
            {card.trend !== undefined && (
              <div className={`flex items-center gap-1 text-xs font-medium ${card.trend > 0 ? 'text-critical' : 'text-success'}`}>
                {card.trend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {Math.abs(card.trend)}%
              </div>
            )}
          </div>
          <div className="font-mono-data text-2xl font-bold text-foreground">{card.value}</div>
          <div className="text-xs text-muted-foreground mt-1">{card.label}</div>
          {card.subtitle && (
            <div className="text-xs text-critical font-mono-data mt-0.5">Score: {card.subtitle}</div>
          )}
        </div>
      ))}
    </div>
  );
}
