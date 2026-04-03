import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { CredibilityBadge, SourceTag } from '@/components/shared/SourceBadge';
import { useLiveData } from '@/hooks/useLiveData';
import { fetchBackendOfficialFeedPosts } from '@/services/backendApi';
import type { OfficialFeedPost } from '@/types/crisis';
import { formatDistanceToNow } from 'date-fns';
import { ExternalLink, RefreshCw, Radio, Send } from 'lucide-react';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

function platformLabel(platform: OfficialFeedPost['platform']): string {
  return platform === 'telegram' ? 'Telegram' : 'X';
}

const severityStyles: Record<OfficialFeedPost['severity'], string> = {
  low: 'border-success/30 bg-success/10 text-success',
  medium: 'border-warning/30 bg-warning/10 text-warning',
  high: 'border-critical/30 bg-critical/10 text-critical',
  critical: 'border-critical/40 bg-critical/20 text-critical',
};

export default function OfficialFeeds() {
  const { incidents, alerts, stats, lastUpdated, connectionStatus } = useLiveData(30000);
  const [posts, setPosts] = useState<OfficialFeedPost[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPosts = async (showToast = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const nextPosts = await fetchBackendOfficialFeedPosts(24);
      setPosts(nextPosts);
      if (showToast) {
        toast.success(`Official feeds refreshed: ${nextPosts.length} posts loaded`);
      }
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : 'Unable to load official outlet feeds.';
      setError(message);
      if (showToast) {
        toast.error(message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadPosts();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadPosts();
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);

  const relevantPosts = posts.filter((post) => post.isSafetyRelevant);

  const groupedPosts = relevantPosts.reduce<Record<string, OfficialFeedPost[]>>((groups, post) => {
    const key = post.publisherName;
    groups[key] = groups[key] ? [...groups[key], post] : [post];
    return groups;
  }, {});

  const publishers = Object.keys(groupedPosts).length;
  const telegramCount = relevantPosts.filter((post) => post.platform === 'telegram').length;
  const topRisk = relevantPosts.reduce((max, post) => Math.max(max, post.riskScore), 0);

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats, lastUpdated, connectionStatus }}>
      <div className="space-y-6">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-primary">
              <Radio className="h-3.5 w-3.5" />
              Official Outlet Feeds
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Newsroom Accounts</h1>
              <p className="max-w-3xl text-sm text-muted-foreground">
                Only direct outlet posts that are both Lebanon-relevant and public-safety relevant are shown here. The same filtered items also feed the shared dashboard and map.
              </p>
            </div>
          </div>
          <button
            onClick={() => { void loadPosts(true); }}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Feeds
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="glass-panel border border-border/50 p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Safety Posts</div>
            <div className="mt-2 text-3xl font-bold text-foreground">{relevantPosts.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Filtered outlet posts that are map-ready and risk-scored.</div>
          </div>
          <div className="glass-panel border border-border/50 p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Covered Publishers</div>
            <div className="mt-2 text-3xl font-bold text-foreground">{publishers}</div>
            <div className="mt-1 text-xs text-muted-foreground">Trusted official outlets contributing safety-relevant posts.</div>
          </div>
          <div className="glass-panel border border-border/50 p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Top Risk Score</div>
            <div className="mt-2 text-3xl font-bold text-foreground">{topRisk.toFixed(0)}</div>
            <div className="mt-1 text-xs text-muted-foreground">{telegramCount} Telegram posts currently pass the Lebanon safety filter.</div>
          </div>
        </div>

        {error ? (
          <div className="glass-panel border border-critical/30 p-5 text-sm text-critical">
            {error}
          </div>
        ) : null}

        {relevantPosts.length === 0 && !isLoading && !error ? (
          <div className="glass-panel border border-border/50 p-6 text-sm text-muted-foreground">
            No official outlet posts currently match the Lebanon public-safety risk filter. Try refreshing in a moment.
          </div>
        ) : null}

        <div className="space-y-6">
          {Object.entries(groupedPosts).map(([publisherName, publisherPosts]) => (
            <section key={publisherName} className="space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-foreground">{publisherName}</h2>
                <span className="rounded-full bg-secondary/60 px-2 py-1 text-[11px] text-muted-foreground">
                  {publisherPosts.length} posts
                </span>
              </div>

              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {publisherPosts.map((post) => (
                  <article key={post.id} className="glass-panel border border-border/50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <SourceTag source={post.sourceInfo} clickable={false} />
                          <CredibilityBadge credibility={post.sourceInfo.credibility} score={post.sourceInfo.credibilityScore} />
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${severityStyles[post.severity]}`}>
                            {post.severity}
                          </span>
                          <span className="rounded-full border border-border/50 bg-secondary/50 px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                            {platformLabel(post.platform)}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <a
                            href={post.accountUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 hover:text-foreground hover:underline"
                          >
                            <Send className="h-3.5 w-3.5" />
                            @{post.accountHandle}
                          </a>
                          <span className="text-muted-foreground/40">•</span>
                          <span>{formatDistanceToNow(new Date(post.publishedAt), { addSuffix: true })}</span>
                          <span className="text-muted-foreground/40">•</span>
                          <span>{post.region}</span>
                          <span className="text-muted-foreground/40">•</span>
                          <span>Risk {post.riskScore.toFixed(0)}</span>
                        </div>
                      </div>
                      <a
                        href={post.postUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-primary/20 bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/20"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                        Open Post
                      </a>
                    </div>

                    <p className="mt-4 whitespace-pre-line text-sm leading-6 text-foreground/85">{post.content}</p>

                    <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                      <span className="rounded-full border border-border/40 bg-secondary/40 px-2 py-1">
                        {post.category.replace(/_/g, ' ')}
                      </span>
                      <span className="rounded-full border border-border/40 bg-secondary/40 px-2 py-1">
                        {post.locationName}
                      </span>
                    </div>

                    {post.signalTags.length > 0 ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {post.signalTags.map((tag) => (
                          <span
                            key={`${post.id}-${tag}`}
                            className="rounded-full border border-border/40 bg-accent/40 px-2 py-1 text-[11px] text-muted-foreground"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}
