import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import type { SourceInfo, Incident } from '@/types/crisis';
import { mockIncidents } from '@/data/mockData';
import { CredibilityMeter } from '@/components/shared/SourceBadge';
import { formatDistanceToNow } from 'date-fns';
import { ExternalLink } from 'lucide-react';

const typeLabels: Record<string, string> = {
  tv: 'Television',
  newspaper: 'Newspaper',
  news_agency: 'News Agency',
  social_media: 'Social Media',
  government: 'Government',
  ngo: 'NGO',
  sensor: 'Sensor Network',
};

const typeIcons: Record<string, string> = {
  tv: '📺', newspaper: '📰', news_agency: '🏛️', social_media: '💬',
  government: '🛡️', ngo: '🏥', sensor: '📡',
};

const severityStyles: Record<string, string> = {
  low: 'bg-success/15 text-success border-success/30',
  medium: 'bg-warning/15 text-warning border-warning/30',
  high: 'bg-critical/15 text-critical border-critical/30',
  critical: 'bg-critical/20 text-critical border-critical/40',
};

export function SourceDetailDialog({
  source,
  open,
  onOpenChange,
}: {
  source: SourceInfo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!source) return null;

  const relatedIncidents = mockIncidents.filter(
    (inc) =>
      inc.sourceInfo.name === source.name ||
      inc.corroboratedBy?.some((s) => s.name === source.name)
  );

  const primaryReported = relatedIncidents.filter((inc) => inc.sourceInfo.name === source.name);
  const corroboratedOnly = relatedIncidents.filter(
    (inc) => inc.sourceInfo.name !== source.name && inc.corroboratedBy?.some((s) => s.name === source.name)
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg bg-card border-border text-foreground max-h-[85vh] overflow-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center text-lg font-bold text-primary">
              {source.logoInitials}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span>{source.name}</span>
                {source.url && (
                  <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/80">
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
              <div className="text-xs text-muted-foreground font-normal flex items-center gap-1.5">
                <span>{typeIcons[source.type]}</span>
                <span>{typeLabels[source.type] || source.type}</span>
              </div>
            </div>
          </DialogTitle>
        </DialogHeader>

        {/* Credibility section */}
        <div className="space-y-4 mt-2">
          <div className="glass-panel p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Credibility Score</span>
              <span className="text-lg font-mono-data font-bold text-foreground">{source.credibilityScore}/100</span>
            </div>
            <CredibilityMeter score={source.credibilityScore} />
            {source.verifiedBy && source.verifiedBy.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap pt-1">
                <span className="text-[9px] text-success/70 uppercase tracking-wider">Verified by:</span>
                {source.verifiedBy.map((v, i) => (
                  <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-success/10 text-success border border-success/20 font-medium">
                    {v}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-2">
            <div className="glass-panel p-2 text-center">
              <div className="text-lg font-mono-data font-bold text-foreground">{primaryReported.length}</div>
              <div className="text-[9px] text-muted-foreground uppercase">Primary Reports</div>
            </div>
            <div className="glass-panel p-2 text-center">
              <div className="text-lg font-mono-data font-bold text-foreground">{corroboratedOnly.length}</div>
              <div className="text-[9px] text-muted-foreground uppercase">Corroborated</div>
            </div>
            <div className="glass-panel p-2 text-center">
              <div className="text-lg font-mono-data font-bold text-foreground">{relatedIncidents.length}</div>
              <div className="text-[9px] text-muted-foreground uppercase">Total Linked</div>
            </div>
          </div>

          {/* Primary reported incidents */}
          {primaryReported.length > 0 && (
            <div>
              <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                Reported by {source.name}
              </h4>
              <div className="space-y-2">
                {primaryReported.map((inc) => (
                  <IncidentRow key={inc.id} incident={inc} />
                ))}
              </div>
            </div>
          )}

          {/* Corroborated incidents */}
          {corroboratedOnly.length > 0 && (
            <div>
              <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                Corroborated by {source.name}
              </h4>
              <div className="space-y-2">
                {corroboratedOnly.map((inc) => (
                  <IncidentRow key={inc.id} incident={inc} showPrimarySource />
                ))}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function IncidentRow({ incident, showPrimarySource = false }: { incident: Incident; showPrimarySource?: boolean }) {
  return (
    <div className="bg-secondary/20 rounded-lg p-2.5 border border-border/20 hover:bg-secondary/30 transition-colors">
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <span className={`text-[9px] px-1.5 py-0.5 rounded border font-bold uppercase tracking-wider ${severityStyles[incident.severity]}`}>
          {incident.severity}
        </span>
        <span className="text-[10px] text-muted-foreground">{incident.region}</span>
        <span className="text-muted-foreground/30">•</span>
        <span className="text-[10px] text-muted-foreground">
          {formatDistanceToNow(new Date(incident.createdAt), { addSuffix: true })}
        </span>
      </div>
      <h5 className="text-xs font-medium text-foreground">{incident.title}</h5>
      <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{incident.description}</p>
      {showPrimarySource && (
        <div className="flex items-center gap-1 mt-1.5 text-[9px] text-muted-foreground/70">
          <span>Primary source:</span>
          <span className="font-semibold text-foreground/60">{incident.sourceInfo.name}</span>
        </div>
      )}
      <div className="flex items-center gap-3 mt-1 text-[10px] text-muted-foreground">
        <span className="font-mono-data">Risk: {incident.riskScore}</span>
        <span className="font-mono-data">Sentiment: {incident.sentimentScore.toFixed(2)}</span>
      </div>
    </div>
  );
}
