import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { mockAlerts } from '@/data/mockData';
import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { ChevronDown, ChevronUp, CheckCircle2, AlertTriangle, AlertOctagon, Info, Siren } from 'lucide-react';
import type { AlertSeverity } from '@/types/crisis';

const tabs = ['All', 'Emergency', 'Critical', 'Warning', 'Acknowledged'] as const;

const severityConfig: Record<AlertSeverity, { icon: typeof AlertTriangle; color: string; bg: string; border: string }> = {
  emergency: { icon: Siren, color: 'text-critical', bg: 'bg-critical/10', border: 'border-critical/30 glow-critical' },
  critical: { icon: AlertOctagon, color: 'text-critical', bg: 'bg-critical/10', border: 'border-critical/20' },
  warning: { icon: AlertTriangle, color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/20' },
  info: { icon: Info, color: 'text-info', bg: 'bg-info/10', border: 'border-info/20' },
};

export default function Alerts() {
  const [activeTab, setActiveTab] = useState<typeof tabs[number]>('All');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const filtered = mockAlerts.filter((a) => {
    if (activeTab === 'All') return true;
    if (activeTab === 'Acknowledged') return a.isAcknowledged;
    return a.severity === activeTab.toLowerCase();
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-foreground">Alerts</h1>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono-data">{mockAlerts.filter((a) => !a.isAcknowledged).length}</span>
            <span>unacknowledged</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-border/50 pb-px">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab}
              {tab !== 'All' && tab !== 'Acknowledged' && (
                <span className="ml-1.5 font-mono-data">
                  ({mockAlerts.filter((a) => a.severity === tab.toLowerCase()).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Alert list */}
        <div className="space-y-3">
          {filtered.map((alert) => {
            const config = severityConfig[alert.severity];
            const Icon = config.icon;
            const isExpanded = expandedId === alert.id;

            return (
              <div
                key={alert.id}
                className={`glass-panel border ${config.border} overflow-hidden animate-fade-in-up`}
              >
                <button
                  onClick={() => setExpandedId(isExpanded ? null : alert.id)}
                  className="w-full text-left p-4 flex items-start gap-4"
                >
                  <div className={`p-2 rounded-lg ${config.bg} shrink-0`}>
                    <Icon className={`w-5 h-5 ${config.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold uppercase tracking-wider ${config.color} ${config.bg} ${config.border}`}>
                        {alert.severity}
                      </span>
                      <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-secondary/50">{alert.alertType.replace('_', ' ')}</span>
                      {alert.isAcknowledged && (
                        <CheckCircle2 className="w-3.5 h-3.5 text-success" />
                      )}
                    </div>
                    <h3 className="text-sm font-semibold text-foreground">{alert.title}</h3>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-muted-foreground">
                      <span>{alert.region}</span>
                      <span className="text-muted-foreground/30">•</span>
                      <span>{formatDistanceToNow(new Date(alert.createdAt), { addSuffix: true })}</span>
                    </div>
                  </div>
                  {isExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground shrink-0 mt-1" /> : <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0 mt-1" />}
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 space-y-4 border-t border-border/30 pt-4 animate-fade-in-up">
                    <div>
                      <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Situation</h4>
                      <p className="text-sm text-foreground/80">{alert.message}</p>
                    </div>
                    <div>
                      <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">AI Recommendation</h4>
                      <div className="bg-secondary/30 rounded-lg p-3 border border-border/30">
                        {alert.recommendation.split('\n').map((line, i) => (
                          <p key={i} className="text-sm text-foreground/80 leading-relaxed">{line}</p>
                        ))}
                      </div>
                    </div>
                    {!alert.isAcknowledged && (
                      <button className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors">
                        Acknowledge Alert
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </DashboardLayout>
  );
}
