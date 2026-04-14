import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useLiveData } from '@/hooks/useLiveData';
import { useState, useEffect, useCallback } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  ShieldAlert, AlertTriangle, RefreshCw, Eye, CheckCircle2,
  XCircle, BarChart3, Globe, Hash, Clock, TrendingUp, Zap,
  ExternalLink, Filter,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchHateSpeechStats,
  fetchHateSpeechPosts,
  fetchHateSpeechAllPosts,
  triggerHateSpeechScan,
  reviewHateSpeechPost,
  type HateSpeechPost,
  type HateSpeechStats,
} from '@/services/backendApi';

// ── Category config ────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  sectarian:       { label: 'Sectarian',        color: 'text-red-400',    bg: 'bg-red-500/10' },
  anti_refugee:    { label: 'Anti-Refugee',      color: 'text-orange-400', bg: 'bg-orange-500/10' },
  political_incite:{ label: 'Political Incite',  color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  misogynistic:    { label: 'Misogynistic',      color: 'text-purple-400', bg: 'bg-purple-500/10' },
  general:         { label: 'General Hate',      color: 'text-pink-400',   bg: 'bg-pink-500/10' },
  clean:           { label: 'Clean',             color: 'text-green-400',  bg: 'bg-green-500/10' },
};

const LANG_FLAGS: Record<string, string> = { ar: '🇦🇷', en: '🇬🇧', fr: '🇫🇷', other: '🌐' };

function scoreColor(score: number): string {
  if (score >= 80) return 'text-red-400';
  if (score >= 60) return 'text-orange-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-green-400';
}

function scoreBg(score: number): string {
  if (score >= 80) return 'bg-red-500/20';
  if (score >= 60) return 'bg-orange-500/20';
  if (score >= 40) return 'bg-yellow-500/20';
  return 'bg-green-500/20';
}

// ── Stat card ──────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string;
  icon: typeof ShieldAlert; color: string;
}) {
  return (
    <div className="glass-panel p-4 flex items-start gap-3">
      <div className={`p-2 rounded-lg ${color}/10 shrink-0`}>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-foreground font-mono-data">{value}</p>
        {sub && <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Post card ─────────────────────────────────────────────────────────────────

function PostCard({
  post,
  onReview,
}: {
  post: HateSpeechPost;
  onReview: (id: string, action: 'confirmed' | 'dismissed') => void;
}) {
  const catCfg = CATEGORY_CONFIG[post.category] ?? CATEGORY_CONFIG.general;
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`glass-panel border border-border/50 overflow-hidden transition-all ${post.reviewed ? 'opacity-60' : ''}`}>
      {/* Header row */}
      <button className="w-full text-left p-4 flex items-start gap-3" onClick={() => setExpanded(!expanded)}>
        {/* Score badge */}
        <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-lg shrink-0 ${scoreBg(post.hateScore)}`}>
          <span className={`text-lg font-bold font-mono-data ${scoreColor(post.hateScore)}`}>
            {Math.round(post.hateScore)}
          </span>
          <span className="text-[9px] text-muted-foreground">score</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-xs font-semibold text-foreground">@{post.authorHandle}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${catCfg.bg} ${catCfg.color}`}>
              {catCfg.label}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {LANG_FLAGS[post.language] ?? '🌐'} {post.language.toUpperCase()}
            </span>
            {post.reviewed && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                post.reviewAction === 'confirmed' ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'
              }`}>
                {post.reviewAction === 'confirmed' ? '✓ Confirmed' : '✗ Dismissed'}
              </span>
            )}
          </div>

          {/* Content preview */}
          <p className="text-xs text-muted-foreground line-clamp-2 text-left" dir="auto">
            {post.content}
          </p>

          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDistanceToNow(new Date(post.postedAt), { addSuffix: true })}
            </span>
            {post.engagementTotal > 0 && (
              <span className="flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                {post.engagementTotal.toLocaleString()} engagements
              </span>
            )}
            {post.keywordMatches.length > 0 && (
              <span className="flex items-center gap-1">
                <Hash className="w-3 h-3" />
                {post.keywordMatches.slice(0, 3).join(', ')}
              </span>
            )}
          </div>
        </div>

        {/* Confidence bar */}
        <div className="shrink-0 text-right hidden sm:block">
          <p className="text-[10px] text-muted-foreground mb-1">Confidence</p>
          <div className="w-16 h-1.5 rounded-full bg-border/50">
            <div
              className={`h-1.5 rounded-full ${scoreColor(post.hateScore).replace('text-', 'bg-')}`}
              style={{ width: `${Math.round(post.modelConfidence * 100)}%` }}
            />
          </div>
          <p className={`text-[10px] mt-0.5 font-mono-data ${scoreColor(post.hateScore)}`}>
            {Math.round(post.modelConfidence * 100)}%
          </p>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-border/30 pt-3 space-y-3">
          <p className="text-sm text-foreground" dir="auto">{post.content}</p>

          {post.hashtags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {post.hashtags.map((tag) => (
                <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-mono-data">
                  #{tag}
                </span>
              ))}
            </div>
          )}

          <div className="grid grid-cols-3 gap-2 text-[10px]">
            <div>
              <span className="text-muted-foreground">Likes </span>
              <span className="font-mono-data">{post.likeCount.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Retweets </span>
              <span className="font-mono-data">{post.retweetCount.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Replies </span>
              <span className="font-mono-data">{post.replyCount.toLocaleString()}</span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {post.sourceUrl && (
              <a
                href={post.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-[10px] text-primary hover:underline"
              >
                <ExternalLink className="w-3 h-3" /> View on X
              </a>
            )}
            {!post.reviewed && (
              <>
                <button
                  onClick={() => onReview(post.id, 'confirmed')}
                  className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
                >
                  <AlertTriangle className="w-3 h-3" /> Confirm Hate Speech
                </button>
                <button
                  onClick={() => onReview(post.id, 'dismissed')}
                  className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20 transition-colors"
                >
                  <XCircle className="w-3 h-3" /> Dismiss (False Positive)
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Category breakdown bar ────────────────────────────────────────────────────

function CategoryBar({ stats }: { stats: HateSpeechStats }) {
  const total = Object.values(stats.byCategory).reduce((s, n) => s + n, 0) || 1;
  const entries = Object.entries(stats.byCategory).sort((a, b) => b[1] - a[1]);
  return (
    <div className="glass-panel p-4 space-y-3">
      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
        <BarChart3 className="w-4 h-4 text-primary" /> By Category
      </h3>
      <div className="space-y-2">
        {entries.map(([cat, count]) => {
          const cfg = CATEGORY_CONFIG[cat] ?? CATEGORY_CONFIG.general;
          const pct = Math.round((count / total) * 100);
          return (
            <div key={cat}>
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className={cfg.color}>{cfg.label}</span>
                <span className="text-muted-foreground font-mono-data">{count} ({pct}%)</span>
              </div>
              <div className="h-1.5 rounded-full bg-border/50">
                <div
                  className={`h-1.5 rounded-full ${cfg.color.replace('text-', 'bg-')}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
        {entries.length === 0 && (
          <p className="text-xs text-muted-foreground">No data yet — trigger a scan to populate.</p>
        )}
      </div>
    </div>
  );
}

// ── Language breakdown ────────────────────────────────────────────────────────

function LanguageBreakdown({ stats }: { stats: HateSpeechStats }) {
  const total = Object.values(stats.byLanguage).reduce((s, n) => s + n, 0) || 1;
  return (
    <div className="glass-panel p-4 space-y-3">
      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
        <Globe className="w-4 h-4 text-primary" /> By Language
      </h3>
      <div className="space-y-1.5">
        {Object.entries(stats.byLanguage)
          .sort((a, b) => b[1] - a[1])
          .map(([lang, count]) => (
            <div key={lang} className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-foreground">
                {LANG_FLAGS[lang] ?? '🌐'} {lang.toUpperCase()}
              </span>
              <span className="text-muted-foreground font-mono-data">
                {count} ({Math.round((count / total) * 100)}%)
              </span>
            </div>
          ))}
        {Object.keys(stats.byLanguage).length === 0 && (
          <p className="text-xs text-muted-foreground">No data yet.</p>
        )}
      </div>
    </div>
  );
}

// ── Top keywords ─────────────────────────────────────────────────────────────

function TopKeywords({ stats }: { stats: HateSpeechStats }) {
  return (
    <div className="glass-panel p-4 space-y-3">
      <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
        <Hash className="w-4 h-4 text-primary" /> Top Keywords
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {stats.topKeywords.slice(0, 20).map(([kw, count]) => (
          <span
            key={kw}
            className="text-[10px] px-2 py-0.5 rounded-full bg-warning/10 text-warning border border-warning/20 font-mono-data"
            dir="auto"
          >
            {kw} <span className="text-muted-foreground">({count})</span>
          </span>
        ))}
        {stats.topKeywords.length === 0 && (
          <p className="text-xs text-muted-foreground">No keywords detected yet.</p>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const CATEGORY_FILTERS = ['All', 'sectarian', 'anti_refugee', 'political_incite', 'misogynistic', 'general'] as const;
type CategoryFilter = typeof CATEGORY_FILTERS[number];

export default function HateSpeechMonitor() {
  const { incidents, alerts, stats: liveStats, lastUpdated, connectionStatus } = useLiveData(60000);

  const [hsStats, setHsStats] = useState<HateSpeechStats | null>(null);
  const [posts, setPosts] = useState<HateSpeechPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('All');
  const [showReviewed, setShowReviewed] = useState<boolean | undefined>(undefined);
  const [minScore, setMinScore] = useState(51);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [statsData, postsData] = await Promise.all([
        fetchHateSpeechStats(),
        flaggedOnly
          ? fetchHateSpeechPosts({
              category: categoryFilter === 'All' ? undefined : categoryFilter,
              minScore,
              reviewed: showReviewed,
              limit: 100,
            })
          : fetchHateSpeechAllPosts({ hours: 24, limit: 200 }),
      ]);
      setHsStats(statsData);
      // When showing all, optionally filter by category client-side
      let filtered = postsData;
      if (!flaggedOnly && categoryFilter !== 'All') {
        filtered = postsData.filter((p) => p.category === categoryFilter);
      }
      setPosts(filtered);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load hate speech data');
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, minScore, showReviewed, flaggedOnly]);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 60000);
    return () => clearInterval(interval);
  }, [load]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerHateSpeechScan();
      toast.success('Scan triggered — new results will appear shortly');
      setTimeout(() => void load(), 3000);
    } catch {
      toast.error('Scan failed — check backend logs');
    } finally {
      setScanning(false);
    }
  };

  const handleReview = async (id: string, action: 'confirmed' | 'dismissed') => {
    try {
      await reviewHateSpeechPost(id, action);
      toast.success(action === 'confirmed' ? 'Confirmed as hate speech' : 'Dismissed as false positive');
      setPosts((prev) =>
        prev.map((p) => (p.id === id ? { ...p, reviewed: true, reviewAction: action } : p)),
      );
    } catch {
      toast.error('Review failed');
    }
  };

  const unreviewed = posts.filter((p) => !p.reviewed).length;

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats: liveStats, lastUpdated, connectionStatus }}>
      <div className="space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-500/10">
              <ShieldAlert className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-foreground">Hate Speech Monitor</h1>
              <p className="text-xs text-muted-foreground">
                Lebanese media on X — Arabic · French · English
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hsStats?.lastScanAt && (
              <span className="text-[10px] text-muted-foreground font-mono-data flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Last scan {formatDistanceToNow(new Date(hsStats.lastScanAt), { addSuffix: true })}
              </span>
            )}
            <button
              onClick={() => void load()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <button
              onClick={() => void handleScan()}
              disabled={scanning}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors disabled:opacity-50"
            >
              {scanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
              {scanning ? 'Scanning…' : 'Trigger Scan'}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="glass-panel border border-warning/30 p-4 text-sm text-warning flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
            <span className="text-xs text-muted-foreground ml-2">(Backend may still be loading models or no scan has run yet)</span>
          </div>
        )}

        {/* Stat cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label="Total Scraped"
            value={hsStats?.totalScraped ?? '—'}
            icon={Eye}
            color="text-blue-400"
          />
          <StatCard
            label="Total Flagged"
            value={hsStats?.totalFlagged ?? '—'}
            sub={`${unreviewed} unreviewed`}
            icon={ShieldAlert}
            color="text-red-400"
          />
          <StatCard
            label="Flagged (24h)"
            value={hsStats?.flaggedLast24h ?? '—'}
            icon={TrendingUp}
            color="text-orange-400"
          />
          <StatCard
            label="Flagged (1h)"
            value={hsStats?.flaggedLast1h ?? '—'}
            icon={Zap}
            color="text-yellow-400"
          />
        </div>

        {/* Side panels */}
        {hsStats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <CategoryBar stats={hsStats} />
            <LanguageBreakdown stats={hsStats} />
            <TopKeywords stats={hsStats} />
          </div>
        )}

        {/* Flagged accounts */}
        {hsStats && hsStats.accountsFlagged.length > 0 && (
          <div className="glass-panel p-4 space-y-2">
            <h3 className="text-sm font-semibold text-foreground">Flagged Accounts</h3>
            <div className="flex flex-wrap gap-1.5">
              {hsStats.accountsFlagged.map((handle) => (
                <span key={handle} className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-mono-data">
                  @{handle}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <Filter className="w-4 h-4 text-muted-foreground shrink-0" />

          {/* Flagged only toggle */}
          <button
            onClick={() => setFlaggedOnly(!flaggedOnly)}
            className={`flex items-center gap-1.5 px-3 py-1 text-[10px] font-medium rounded-lg border transition-colors ${
              flaggedOnly
                ? 'bg-red-500/15 text-red-400 border-red-500/30'
                : 'bg-secondary/30 text-muted-foreground border-border/50 hover:text-foreground'
            }`}
          >
            <ShieldAlert className="w-3 h-3" />
            {flaggedOnly ? 'Flagged Only' : 'All Posts'}
          </button>

          {/* Category tabs */}
          <div className="flex gap-1 border border-border/50 rounded-lg p-0.5">
            {CATEGORY_FILTERS.map((cat) => {
              const cfg = cat === 'All' ? null : CATEGORY_CONFIG[cat];
              return (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`px-2.5 py-1 text-[10px] font-medium rounded-md transition-colors ${
                    categoryFilter === cat
                      ? 'bg-primary/15 text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {cfg ? cfg.label : 'All'}
                </button>
              );
            })}
          </div>

          {/* Min score slider */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Min score:</span>
            <input
              type="range"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-20 accent-primary"
            />
            <span className={`font-mono-data font-bold ${scoreColor(minScore)}`}>{minScore}</span>
          </div>

          {/* Reviewed filter */}
          <div className="flex gap-1 border border-border/50 rounded-lg p-0.5">
            {[
              { label: 'All', value: undefined },
              { label: 'Pending', value: false },
              { label: 'Reviewed', value: true },
            ].map((opt) => (
              <button
                key={String(opt.value)}
                onClick={() => setShowReviewed(opt.value)}
                className={`px-2.5 py-1 text-[10px] font-medium rounded-md transition-colors ${
                  showReviewed === opt.value
                    ? 'bg-primary/15 text-primary'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <span className="text-xs text-muted-foreground ml-auto font-mono-data">
            {posts.length} posts shown
          </span>
        </div>

        {/* Post feed */}
        <div className="space-y-2">
          {loading && (
            <div className="glass-panel p-8 text-center text-sm text-muted-foreground">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
              {flaggedOnly ? 'Loading flagged posts…' : 'Loading scraped posts…'}
            </div>
          )}

          {!loading && posts.length === 0 && (
            <div className="glass-panel p-8 text-center space-y-2">
              <CheckCircle2 className="w-8 h-8 text-success mx-auto" />
              <p className="text-sm font-medium text-foreground">
                {flaggedOnly ? 'No flagged posts match your filters' : 'No posts yet — trigger a scan to load real X data'}
              </p>
              <p className="text-xs text-muted-foreground">
                {flaggedOnly
                  ? 'Try lowering the minimum score or switching to "All Posts".'
                  : 'Click "Trigger Scan" to scrape Lebanese media accounts on X.'}
              </p>
            </div>
          )}

          {!loading && posts.map((post) => (
            <PostCard key={post.id} post={post} onReview={handleReview} />
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}
