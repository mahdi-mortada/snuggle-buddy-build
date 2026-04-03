import { formatDistanceToNow } from 'date-fns';
import { CredibilityBadge, SourceTag } from '@/components/shared/SourceBadge';
import { Eye, Share2, Flag, ExternalLink, Radio, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import type { Incident, OfficialFeedPost } from '@/types/crisis';
import { Skeleton } from '@/components/ui/skeleton';
import { openSourceUrl, resolveSourceUrl } from '@/lib/sourceLink';

const severityStyles: Record<string, string> = {
  low: 'bg-success/15 text-success border-success/30',
  medium: 'bg-warning/15 text-warning border-warning/30',
  high: 'bg-critical/15 text-critical border-critical/30',
  critical: 'bg-critical/20 text-critical border-critical/40 glow-critical',
};

const categoryLabels: Record<string, string> = {
  violence: '[V]',
  protest: '[P]',
  natural_disaster: '[N]',
  infrastructure: '[I]',
  health: '[H]',
  terrorism: '[T]',
  cyber: '[C]',
  other: '[O]',
};

export type IncidentFeedItem = {
  id: string;
  type: 'incident';
  title: string;
  description: string;
  timestamp: number;
  source: string;
  incident: Incident;
};

export type TelegramFeedItem = {
  id: string;
  type: 'telegram';
  title: string;
  description: string;
  timestamp: number;
  source: string;
  telegram: OfficialFeedPost;
};

export type LiveFeedItem = IncidentFeedItem | TelegramFeedItem;

type LiveIncidentFeedProps = {
  items: LiveFeedItem[];
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
};

function formatRelativeFromTimestamp(timestamp: number): string {
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return 'unknown time';
  }
  return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
}

export function LiveIncidentFeed({ items, isLoading = false, error = null, onRetry }: LiveIncidentFeedProps) {
  return (
    <div className="glass-panel h-full flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="text-sm font-semibold text-foreground">Live Incident Feed</h3>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono-data text-muted-foreground">{items.length} updates</span>
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-success" />
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Live</span>
          </div>
        </div>
      </div>

      {error && !isLoading ? (
        <div className="px-4 py-3 border-b border-border/40 bg-critical/5 flex items-center justify-between gap-3">
          <p className="text-xs text-critical truncate">{error}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1 rounded border border-primary/20 bg-primary/10 px-2 py-1 text-[10px] text-primary hover:bg-primary/20"
            >
              <RefreshCw className="w-3 h-3" />
              Retry
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="flex-1 overflow-auto scrollbar-thin divide-y divide-border/30">
        {isLoading && items.length === 0 ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={`feed-skeleton-${index}`} className="space-y-2">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-3 w-full" />
              </div>
            ))}
          </div>
        ) : null}

        {!isLoading && items.length === 0 ? (
          <div className="p-4 text-xs text-muted-foreground">No live incidents or Telegram updates yet.</div>
        ) : null}

        {items.map((item, i) => {
          if (item.type === 'telegram') {
            const feed = item.telegram;
            const sourceUrl = resolveSourceUrl(feed);
            return (
              <div
                key={item.id}
                className="px-4 py-3 hover:bg-accent/20 transition-colors animate-slide-in group border-l-2 border-l-primary/30"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="flex items-start gap-3">
                  <span className="text-primary mt-0.5"><Radio className="w-4 h-4" /></span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-[10px] px-1.5 py-0.5 rounded border border-primary/30 bg-primary/10 text-primary font-medium uppercase tracking-wider">
                        telegram
                      </span>
                      <SourceTag source={feed.sourceInfo} clickable={false} />
                      <CredibilityBadge credibility={feed.sourceInfo.credibility} score={feed.sourceInfo.credibilityScore} />
                      <span className="text-[10px] text-muted-foreground">{formatRelativeFromTimestamp(item.timestamp)}</span>
                    </div>
                    <h4 className="text-sm font-medium text-foreground truncate">{item.title}</h4>
                    <p className="text-[11px] text-muted-foreground/80 line-clamp-3 mt-0.5">{item.description}</p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-[11px] text-muted-foreground">{item.source}</span>
                      <span className="text-muted-foreground/30">|</span>
                      <span className="text-[11px] text-muted-foreground">@{feed.accountHandle}</span>
                      {sourceUrl ? (
                        <>
                          <span className="text-muted-foreground/30">|</span>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              openSourceUrl(sourceUrl);
                            }}
                            className="inline-flex items-center gap-1 rounded border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/20 transition-colors"
                          >
                            <ExternalLink className="w-3 h-3" />
                            View Source
                          </button>
                        </>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            );
          }

          const incident = item.incident;
          const sourceUrl = resolveSourceUrl(incident);
          return (
            <div
              key={incident.id}
              className="px-4 py-3 hover:bg-accent/30 transition-colors cursor-pointer animate-slide-in group"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-start gap-3">
                <span className="text-[11px] font-mono-data mt-1 text-muted-foreground">{categoryLabels[incident.category] || '[O]'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase tracking-wider ${severityStyles[incident.severity]}`}>
                      {incident.severity}
                    </span>
                    <SourceTag source={incident.sourceInfo} />
                    <CredibilityBadge credibility={incident.sourceInfo.credibility} score={incident.sourceInfo.credibilityScore} />
                    <span className="text-[10px] text-muted-foreground">
                      {formatDistanceToNow(new Date(incident.createdAt), { addSuffix: true })}
                    </span>
                  </div>
                  <h4 className="text-sm font-medium text-foreground truncate">{incident.title}</h4>
                  <p className="text-[11px] text-muted-foreground/70 truncate mt-0.5">{incident.description}</p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="text-[11px] text-muted-foreground">{incident.region}</span>
                    <span className="text-muted-foreground/30">|</span>
                    <span className="text-[11px] font-mono-data text-muted-foreground">Risk: {incident.riskScore}</span>
                    {sourceUrl ? (
                      <>
                        <span className="text-muted-foreground/30">|</span>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            openSourceUrl(sourceUrl);
                          }}
                          className="inline-flex items-center gap-1 rounded border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/20 transition-colors"
                        >
                          <ExternalLink className="w-3 h-3" />
                          View Source
                        </button>
                      </>
                    ) : null}
                    {incident.corroboratedBy && incident.corroboratedBy.length > 0 && (
                      <>
                        <span className="text-muted-foreground/30">|</span>
                        <span className="text-[10px] text-success/80">
                          Confirmed by {incident.corroboratedBy.length} {incident.corroboratedBy.length === 1 ? 'source' : 'sources'}
                        </span>
                      </>
                    )}
                  </div>
                  {incident.corroboratedBy && incident.corroboratedBy.length > 0 && (
                    <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                      <span className="text-[9px] text-muted-foreground/60 uppercase tracking-wider">Also reported by:</span>
                      {incident.corroboratedBy.map((s, idx) => (
                        <SourceTag key={idx} source={s} showType={false} />
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  {sourceUrl ? (
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        openSourceUrl(sourceUrl);
                      }}
                      className="p-1.5 rounded hover:bg-accent transition-colors"
                      title="Open source"
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-primary" />
                    </button>
                  ) : null}
                  <button
                    onClick={(e) => { e.stopPropagation(); toast.info(`Viewing details for: ${incident.title}`); }}
                    className="p-1.5 rounded hover:bg-accent transition-colors"
                    title="View details"
                  >
                    <Eye className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); toast.success('Incident shared to team channel'); }}
                    className="p-1.5 rounded hover:bg-accent transition-colors"
                    title="Share"
                  >
                    <Share2 className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); toast.warning('Incident flagged for review'); }}
                    className="p-1.5 rounded hover:bg-accent transition-colors"
                    title="Flag"
                  >
                    <Flag className="w-3.5 h-3.5 text-muted-foreground" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
