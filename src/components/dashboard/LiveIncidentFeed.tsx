import { mockIncidents } from '@/data/mockData';
import { formatDistanceToNow } from 'date-fns';

const severityStyles: Record<string, string> = {
  low: 'bg-success/15 text-success border-success/30',
  medium: 'bg-warning/15 text-warning border-warning/30',
  high: 'bg-critical/15 text-critical border-critical/30',
  critical: 'bg-critical/20 text-critical border-critical/40 glow-critical',
};

const categoryIcons: Record<string, string> = {
  violence: '⚔️',
  protest: '✊',
  natural_disaster: '🌊',
  infrastructure: '🏗️',
  health: '🏥',
  terrorism: '💣',
  cyber: '🔒',
  other: '📋',
};

export function LiveIncidentFeed() {
  return (
    <div className="glass-panel h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="text-sm font-semibold text-foreground">Live Incident Feed</h3>
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-success" />
          </span>
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Real-time</span>
        </div>
      </div>
      <div className="flex-1 overflow-auto scrollbar-thin divide-y divide-border/30">
        {mockIncidents.map((incident, i) => (
          <div
            key={incident.id}
            className="px-4 py-3 hover:bg-accent/30 transition-colors cursor-pointer animate-slide-in"
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <div className="flex items-start gap-3">
              <span className="text-lg mt-0.5">{categoryIcons[incident.category] || '📋'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wider ${severityStyles[incident.severity]}`}>
                    {incident.severity}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {formatDistanceToNow(new Date(incident.createdAt), { addSuffix: true })}
                  </span>
                </div>
                <h4 className="text-sm font-medium text-foreground truncate">{incident.title}</h4>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[11px] text-muted-foreground">{incident.region}</span>
                  <span className="text-muted-foreground/30">•</span>
                  <span className="text-[11px] font-mono-data text-muted-foreground">Risk: {incident.riskScore}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
