import type { CredibilityLevel, SourceInfo } from '@/types/crisis';

const credibilityConfig: Record<CredibilityLevel, { label: string; color: string; bg: string; border: string }> = {
  verified: { label: 'Verified', color: 'text-success', bg: 'bg-success/10', border: 'border-success/30' },
  high: { label: 'High', color: 'text-primary', bg: 'bg-primary/10', border: 'border-primary/30' },
  moderate: { label: 'Moderate', color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/30' },
  low: { label: 'Low', color: 'text-critical/70', bg: 'bg-critical/5', border: 'border-critical/20' },
  unverified: { label: 'Unverified', color: 'text-muted-foreground', bg: 'bg-secondary/30', border: 'border-border/30' },
};

const typeIcons: Record<string, string> = {
  tv: '📺',
  newspaper: '📰',
  news_agency: '🏛️',
  social_media: '💬',
  government: '🛡️',
  ngo: '🏥',
  sensor: '📡',
};

export function CredibilityBadge({ credibility, score }: { credibility: CredibilityLevel; score: number }) {
  const config = credibilityConfig[credibility];
  return (
    <span className={`inline-flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border font-semibold uppercase tracking-wider ${config.color} ${config.bg} ${config.border}`}>
      <span className="font-mono-data">{score}</span>
      <span className="opacity-60">•</span>
      {config.label}
    </span>
  );
}

export function SourceTag({ source, showType = true }: { source: SourceInfo; showType?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-accent/40 text-foreground/80 border border-border/30 font-medium">
      {showType && <span className="text-[9px]">{typeIcons[source.type] || '📋'}</span>}
      <span className="font-semibold">{source.logoInitials}</span>
      <span className="opacity-60">|</span>
      <span>{source.name}</span>
    </span>
  );
}

export function CredibilityMeter({ score }: { score: number }) {
  const getColor = () => {
    if (score >= 80) return 'bg-success';
    if (score >= 60) return 'bg-primary';
    if (score >= 40) return 'bg-warning';
    return 'bg-critical';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-secondary/50 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${getColor()}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-[10px] font-mono-data text-muted-foreground w-6 text-right">{score}</span>
    </div>
  );
}
