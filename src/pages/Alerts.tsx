import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { mockAlerts, mockIncidents } from '@/data/mockData';
import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { ChevronDown, ChevronUp, CheckCircle2, AlertTriangle, AlertOctagon, Info, Siren, Share2, Download, Bell, BellOff } from 'lucide-react';
import type { AlertSeverity } from '@/types/crisis';
import { SourceTag, CredibilityBadge } from '@/components/shared/SourceBadge';
import { toast } from 'sonner';

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
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set(mockAlerts.filter(a => a.isAcknowledged).map(a => a.id)));

  const filtered = mockAlerts.filter((a) => {
    if (activeTab === 'All') return true;
    if (activeTab === 'Acknowledged') return acknowledged.has(a.id);
    return a.severity === activeTab.toLowerCase();
  });

  const handleAcknowledge = (id: string) => {
    setAcknowledged(prev => new Set([...prev, id]));
    toast.success('Alert acknowledged');
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h1 className="text-xl font-bold text-foreground">Alerts</h1>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-mono-data">{mockAlerts.length - acknowledged.size} unacknowledged</span>
            <button onClick={() => { setAcknowledged(new Set(mockAlerts.map(a => a.id))); toast.success('All alerts acknowledged'); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-success/10 text-success border border-success/20 hover:bg-success/20 transition-colors">
              <CheckCircle2 className="w-3.5 h-3.5" /> Acknowledge All
            </button>
            <button onClick={() => toast.success('Alert report exported')}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors">
              <Download className="w-3.5 h-3.5" /> Export
            </button>
          </div>
        </div>

        <div className="flex gap-1 border-b border-border/50 pb-px">
          {tabs.map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${activeTab === tab ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
              {tab}
              {tab !== 'All' && tab !== 'Acknowledged' && (
                <span className="ml-1.5 font-mono-data">({mockAlerts.filter((a) => a.severity === tab.toLowerCase()).length})</span>
              )}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {filtered.map((alert) => {
            const config = severityConfig[alert.severity];
            const Icon = config.icon;
            const isExpanded = expandedId === alert.id;
            const isAck = acknowledged.has(alert.id);

            return (
              <div key={alert.id} className={`glass-panel border ${config.border} overflow-hidden animate-fade-in-up`}>
                <button onClick={() => setExpandedId(isExpanded ? null : alert.id)} className="w-full text-left p-4 flex items-start gap-4">
                  <div className={`p-2 rounded-lg ${config.bg} shrink-0`}><Icon className={`w-5 h-5 ${config.color}`} /></div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold uppercase tracking-wider ${config.color} ${config.bg} ${config.border}`}>{alert.severity}</span>
                      <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-secondary/50">{alert.alertType.replace('_', ' ')}</span>
                      {isAck && <CheckCircle2 className="w-3.5 h-3.5 text-success" />}
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

                    {alert.linkedIncidents.length > 0 && (() => {
                      const linkedIncidents = alert.linkedIncidents.map(id => mockIncidents.find(inc => inc.id === id)).filter(Boolean);
                      if (linkedIncidents.length === 0) return null;
                      return (
                        <div>
                          <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Sources & Credibility</h4>
                          <div className="space-y-2">
                            {linkedIncidents.map(inc => inc && (
                              <div key={inc.id} className="bg-secondary/20 rounded-lg p-2.5 border border-border/20">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <SourceTag source={inc.sourceInfo} />
                                  <CredibilityBadge credibility={inc.sourceInfo.credibility} score={inc.sourceInfo.credibilityScore} />
                                  {inc.sourceInfo.verifiedBy && (
                                    <span className="text-[9px] text-success/70">Verified by: {inc.sourceInfo.verifiedBy.join(', ')}</span>
                                  )}
                                </div>
                                {inc.corroboratedBy && inc.corroboratedBy.length > 0 && (
                                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                                    <span className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Corroborated by:</span>
                                    {inc.corroboratedBy.map((s, idx) => (
                                      <SourceTag key={idx} source={s} showType={false} />
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    <div>
                      <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">AI Recommendation</h4>
                      <div className="bg-secondary/30 rounded-lg p-3 border border-border/30">
                        {alert.recommendation.split('\n').map((line, i) => (
                          <p key={i} className="text-sm text-foreground/80 leading-relaxed">{line}</p>
                        ))}
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {!isAck && (
                        <button onClick={() => handleAcknowledge(alert.id)}
                          className="flex items-center gap-1.5 px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors">
                          <CheckCircle2 className="w-4 h-4" /> Acknowledge
                        </button>
                      )}
                      <button onClick={() => toast.success('Alert shared to team')}
                        className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors">
                        <Share2 className="w-3.5 h-3.5" /> Share
                      </button>
                      <button onClick={() => toast.info(isAck ? 'Notifications re-enabled' : 'Alert muted')}
                        className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors">
                        {isAck ? <Bell className="w-3.5 h-3.5" /> : <BellOff className="w-3.5 h-3.5" />}
                        {isAck ? 'Unmute' : 'Mute'}
                      </button>
                      <button onClick={() => toast.success('Escalated to command center')}
                        className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-critical/10 text-critical border border-critical/20 hover:bg-critical/20 transition-colors">
                        <Siren className="w-3.5 h-3.5" /> Escalate
                      </button>
                    </div>
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
