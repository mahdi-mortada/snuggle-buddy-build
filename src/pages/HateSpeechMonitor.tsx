import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useLiveData } from '@/hooks/useLiveData';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  ShieldAlert, AlertTriangle, RefreshCw, XCircle, Hash, Clock,
  TrendingUp, Zap, ExternalLink, MessageSquare, Heart, Repeat2,
  ChevronDown, ChevronUp, X, Loader2, Flame, BarChart2, ArrowUpRight,
  Search, Trash2, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchHateSpeechStats,
  fetchHateSpeechAllPosts,
  triggerHateSpeechScan,
  reviewHateSpeechPost,
  fetchHateSpeechReplies,
  fetchHateSpeechAgentStatus,
  fetchHateSpeechSearch,
  deleteHateSpeechTrend,
  type HateSpeechPost,
  type HateSpeechStats,
  type HateSpeechReply,
  type HateSpeechTrendCluster,
  type HateSpeechSortOption,
  type HateSpeechAgentStatus,
} from '@/services/backendApi';

// ── Config ─────────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; labelAr: string; color: string; bg: string }> = {
  sectarian:        { label: 'Sectarian',        labelAr: 'طائفي',         color: 'text-red-400',    bg: 'bg-red-500/10' },
  anti_refugee:     { label: 'Anti-Refugee',     labelAr: 'ضد اللاجئين',   color: 'text-orange-400', bg: 'bg-orange-500/10' },
  political_incite: { label: 'Political Incite', labelAr: 'تحريض سياسي',  color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  misogynistic:     { label: 'Misogynistic',     labelAr: 'كراهية المرأة', color: 'text-purple-400', bg: 'bg-purple-500/10' },
  general:          { label: 'General Hate',     labelAr: 'كراهية عامة',   color: 'text-pink-400',   bg: 'bg-pink-500/10' },
  clean:            { label: 'Clean',            labelAr: 'نظيف',          color: 'text-green-400',  bg: 'bg-green-500/10' },
};

const RISK_LEVEL_CONFIG = {
  critical: { label: 'خطر حرج',   color: 'text-red-400',    bg: 'bg-red-500/15',    border: 'border-red-500/30',    dot: 'bg-red-400' },
  high:     { label: 'خطر عالٍ',  color: 'text-orange-400', bg: 'bg-orange-500/15', border: 'border-orange-500/30', dot: 'bg-orange-400' },
  medium:   { label: 'خطر متوسط', color: 'text-yellow-400', bg: 'bg-yellow-500/15', border: 'border-yellow-500/30', dot: 'bg-yellow-400' },
  low:      { label: 'خطر منخفض', color: 'text-green-400',  bg: 'bg-green-500/15',  border: 'border-green-500/30',  dot: 'bg-green-400' },
} as const;

const SORT_OPTIONS: { key: HateSpeechSortOption; label: string; labelAr: string; icon: React.FC<{ className?: string }> }[] = [
  { key: 'priority',   label: 'Priority',    labelAr: 'الأولوية',    icon: ShieldAlert },
  { key: 'velocity',   label: 'Trending',    labelAr: 'رائج الآن',   icon: Flame },
  { key: 'score',      label: 'Risk Score',  labelAr: 'درجة الخطر',  icon: BarChart2 },
  { key: 'engagement', label: 'Engagement',  labelAr: 'التفاعل',     icon: Heart },
  { key: 'recent',     label: 'Recent',      labelAr: 'الأحدث',      icon: Clock },
];

const LANG_TABS = [
  { key: 'ar',  label: 'العربية', flag: '🇱🇧' },
  { key: 'all', label: 'الكل',    flag: '🌐' },
] as const;
type LangTab = typeof LANG_TABS[number]['key'];

function scoreColor(s: number) {
  if (s >= 80) return 'text-red-400';
  if (s >= 60) return 'text-orange-400';
  if (s >= 40) return 'text-yellow-400';
  return 'text-green-400';
}
function scoreBg(s: number) {
  if (s >= 80) return 'bg-red-500/20 border-red-500/30';
  if (s >= 60) return 'bg-orange-500/20 border-orange-500/30';
  if (s >= 40) return 'bg-yellow-500/20 border-yellow-500/30';
  return 'bg-emerald-500/20 border-emerald-500/30';
}

// ── Replies Modal ─────────────────────────────────────────────────────────────

function RepliesModal({ post, onClose }: { post: HateSpeechPost; onClose: () => void }) {
  const [replies, setReplies] = useState<HateSpeechReply[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const isAr = post.language === 'ar';

  useEffect(() => {
    void (async () => {
      try {
        const data = await fetchHateSpeechReplies(post.id, 10);
        setReplies(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'فشل تحميل التعليقات');
      } finally {
        setLoading(false);
      }
    })();
  }, [post.id]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="glass-panel w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden border border-border/60 shadow-2xl">
        {/* Header */}
        <div className="flex items-start gap-3 p-4 border-b border-border/40 shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-xs font-semibold text-foreground">@{post.authorHandle}</span>
              <span className="text-[10px] text-muted-foreground">·</span>
              <span className="text-[10px] text-muted-foreground">
                {formatDistanceToNow(new Date(post.postedAt), { addSuffix: true })}
              </span>
              {post.matchedTrend && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center gap-0.5">
                  <TrendingUp className="w-2.5 h-2.5" /> #{post.matchedTrend}
                </span>
              )}
              {post.sourceUrl && (
                <a
                  href={post.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] text-primary flex items-center gap-0.5 hover:underline ml-auto"
                >
                  <ExternalLink className="w-3 h-3" /> عرض على X
                </a>
              )}
            </div>
            <p
              className={`text-sm leading-relaxed text-foreground/90 ${isAr ? 'text-right' : ''}`}
              dir={isAr ? 'rtl' : 'ltr'}
            >
              {post.content}
            </p>
            <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-0.5 text-pink-400">
                <Heart className="w-3 h-3" /> {post.likeCount.toLocaleString()}
              </span>
              <span className="flex items-center gap-0.5">
                <Repeat2 className="w-3 h-3" /> {post.retweetCount.toLocaleString()}
              </span>
              <span className="flex items-center gap-0.5 text-primary">
                <MessageSquare className="w-3 h-3" /> {post.replyCount.toLocaleString()} تعليق
              </span>
            </div>
          </div>
          <button onClick={onClose} className="shrink-0 p-1.5 rounded-lg hover:bg-secondary/50 text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Replies */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-primary" /> أكثر التعليقات تفاعلاً
          </h3>
          {loading && (
            <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground text-sm">
              <Loader2 className="w-4 h-4 animate-spin" /> جارٍ تحميل التعليقات…
            </div>
          )}
          {error && !loading && (
            <div className="text-center py-8 text-muted-foreground text-xs">
              <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-warning" />
              {error}
            </div>
          )}
          {!loading && !error && replies.length === 0 && (
            <div className="text-center py-10 text-muted-foreground text-xs">
              <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-40" /> لا توجد تعليقات متاحة
            </div>
          )}
          {!loading && replies.map((reply, idx) => {
            const replyIsAr = reply.language === 'ar';
            return (
              <div key={reply.id} className="glass-panel border border-border/30 p-3 space-y-2 hover:border-border/50">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-foreground/80">#{idx + 1}</span>
                  <span className="text-xs font-semibold text-foreground">@{reply.authorHandle}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground">
                    {formatDistanceToNow(new Date(reply.postedAt), { addSuffix: true })}
                  </span>
                </div>
                <p className={`text-sm leading-relaxed text-foreground/90 ${replyIsAr ? 'text-right' : ''}`} dir={replyIsAr ? 'rtl' : 'ltr'}>
                  {reply.content}
                </p>
                <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-0.5 text-pink-400 font-semibold">
                    <Heart className="w-3 h-3" /> {reply.likeCount.toLocaleString()}
                  </span>
                  <span className="flex items-center gap-0.5">
                    <Repeat2 className="w-3 h-3" /> {reply.retweetCount.toLocaleString()}
                  </span>
                  {reply.sourceUrl && (
                    <a href={reply.sourceUrl} target="_blank" rel="noopener noreferrer"
                      className="text-primary flex items-center gap-0.5 hover:underline ml-auto">
                      <ExternalLink className="w-3 h-3" /> رابط
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Post card ─────────────────────────────────────────────────────────────────

function PostCard({
  post,
  activeHashtag,
  activeTrend,
  onReview,
  onOpenReplies,
  onHashtagClick,
  onTrendClick,
}: {
  post: HateSpeechPost;
  activeHashtag: string | null;
  activeTrend: string | null;
  onReview: (id: string, action: 'confirmed' | 'dismissed') => void;
  onOpenReplies: (post: HateSpeechPost) => void;
  onHashtagClick: (tag: string) => void;
  onTrendClick: (trend: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const catCfg = CATEGORY_CONFIG[post.category] ?? CATEGORY_CONFIG.general;
  const isAr = post.language === 'ar';
  const isHighVelocity = post.engagementVelocity >= 20;
  const isViral = post.engagementVelocity >= 50;
  const isHighlighted =
    (activeHashtag && post.hashtags.includes(activeHashtag.toLowerCase())) ||
    (activeTrend && post.matchedTrend.toLowerCase() === activeTrend.toLowerCase());

  return (
    <div
      className={`glass-panel border overflow-hidden transition-all duration-200 ${
        post.reviewed ? 'opacity-50' : ''
      } ${
        isHighlighted
          ? 'border-primary/50 shadow-[0_0_0_1px_rgba(var(--primary),0.2)]'
          : 'border-border/40 hover:border-border/70'
      }`}
    >
      <button
        className="w-full text-left p-4 cursor-pointer"
        onClick={() => onOpenReplies(post)}
        title="انقر لعرض التعليقات"
      >
        <div className="flex items-start gap-3">
          {/* Score pill */}
          <div className={`flex flex-col items-center justify-center min-w-[48px] h-12 rounded-xl border shrink-0 ${scoreBg(post.hateScore)}`}>
            <span className={`text-base font-bold font-mono-data leading-none ${scoreColor(post.hateScore)}`}>
              {Math.round(post.hateScore)}
            </span>
            <span className="text-[8px] text-muted-foreground mt-0.5 uppercase tracking-wide">score</span>
          </div>

          <div className="flex-1 min-w-0">
            {/* Meta row */}
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              <span className="text-xs font-semibold text-foreground">@{post.authorHandle}</span>

              {post.category !== 'clean' && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium ${catCfg.bg} ${catCfg.color}`}>
                  {isAr ? catCfg.labelAr : catCfg.label}
                </span>
              )}

              {/* Velocity badge */}
              {isViral && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-md font-medium bg-rose-500/15 text-rose-400 border border-rose-500/20 flex items-center gap-0.5">
                  <Flame className="w-2.5 h-2.5" /> فيروسي
                </span>
              )}
              {!isViral && isHighVelocity && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-md font-medium bg-amber-500/15 text-amber-400 border border-amber-500/20 flex items-center gap-0.5">
                  <ArrowUpRight className="w-2.5 h-2.5" /> رائج
                </span>
              )}

              {post.reviewed && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium ${
                  post.reviewAction === 'confirmed' ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'
                }`}>
                  {post.reviewAction === 'confirmed' ? '✓ مؤكد' : '✗ مرفوض'}
                </span>
              )}

              <span className="ml-auto text-[10px] text-muted-foreground flex items-center gap-1 shrink-0">
                <Clock className="w-3 h-3" />
                {formatDistanceToNow(new Date(post.postedAt), { addSuffix: true })}
              </span>
            </div>

            {/* Content */}
            <p
              className={`text-sm leading-relaxed line-clamp-3 text-foreground/90 ${isAr ? 'text-right' : ''}`}
              dir={isAr ? 'rtl' : 'ltr'}
              lang={post.language}
            >
              {post.content}
            </p>

            {/* Engagement + trend + hashtag row */}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {post.likeCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                  <Heart className="w-3 h-3 text-pink-400" /> {post.likeCount.toLocaleString()}
                </span>
              )}
              {post.retweetCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                  <Repeat2 className="w-3 h-3" /> {post.retweetCount.toLocaleString()}
                </span>
              )}
              {post.replyCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] text-primary">
                  <MessageSquare className="w-3 h-3" /> {post.replyCount.toLocaleString()}
                </span>
              )}
              {/* Matched trend chip */}
              {post.matchedTrend && (
                <span
                  onClick={(e) => { e.stopPropagation(); onTrendClick(post.matchedTrend); }}
                  className={`text-[10px] px-1.5 py-0.5 rounded-full cursor-pointer font-medium flex items-center gap-0.5 transition-colors ${
                    activeTrend === post.matchedTrend
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-primary/15 text-primary border border-primary/25 hover:bg-primary/25'
                  }`}
                >
                  <TrendingUp className="w-2.5 h-2.5" /> {post.matchedTrend}
                </span>
              )}
              {/* Inline hashtag chips */}
              {post.hashtags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  onClick={(e) => { e.stopPropagation(); onHashtagClick(tag); }}
                  className={`text-[10px] px-1.5 py-0.5 rounded-full cursor-pointer font-mono-data transition-colors ${
                    activeHashtag === tag
                      ? 'bg-secondary text-foreground'
                      : 'bg-secondary/50 text-muted-foreground hover:bg-secondary/80 border border-border/30'
                  }`}
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          {/* Expand toggle */}
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            className="shrink-0 p-1 text-muted-foreground hover:text-foreground mt-1"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </button>

      {/* Expanded actions */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-border/20 pt-3 flex items-center gap-2 flex-wrap">
          {/* Priority score detail */}
          <span className="text-[10px] text-muted-foreground font-mono-data">
            أولوية: <span className="text-foreground font-semibold">{post.priorityScore}</span>
            {post.engagementVelocity > 0 && (
              <> · سرعة: <span className="text-amber-400">{post.engagementVelocity.toFixed(1)}/hr</span></>
            )}
          </span>
          {post.sourceUrl && (
            <a
              href={post.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[10px] text-primary hover:underline"
            >
              <ExternalLink className="w-3 h-3" /> عرض على X
            </a>
          )}
          {!post.reviewed && (
            <>
              <button
                onClick={() => onReview(post.id, 'confirmed')}
                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20"
              >
                <AlertTriangle className="w-3 h-3" /> تأكيد كخطاب كراهية
              </button>
              <button
                onClick={() => onReview(post.id, 'dismissed')}
                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20"
              >
                <XCircle className="w-3 h-3" /> تجاهل (إيجابي كاذب)
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Trend cluster panel ───────────────────────────────────────────────────────

function TrendClusterPanel({
  clusters,
  activeTrend,
  onTrendClick,
  onHideTrend,
  hiddenCount,
  onRestoreAll,
  onDeleteTrend,
}: {
  clusters: HateSpeechTrendCluster[];
  activeTrend: string | null;
  onTrendClick: (trend: string | null) => void;
  onHideTrend: (trend: string) => void;
  hiddenCount: number;
  onRestoreAll: () => void;
  onDeleteTrend: (trend: string) => void;
}) {
  if (clusters.length === 0 && hiddenCount === 0) return null;
  return (
    <div className="glass-panel p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <TrendingUp className="w-3.5 h-3.5 text-primary" />
          الترندات الرائجة في لبنان
          <span className="text-[10px] text-muted-foreground font-normal">· اضغط للتصفية</span>
        </h3>
        <div className="flex items-center gap-2">
          {hiddenCount > 0 && (
            <button
              onClick={onRestoreAll}
              className="text-[10px] text-primary/70 hover:text-primary flex items-center gap-1 transition-colors"
            >
              استعادة الكل ({hiddenCount})
            </button>
          )}
          {activeTrend && (
            <button
              onClick={() => onTrendClick(null)}
              className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <X className="w-3 h-3" /> إلغاء
            </button>
          )}
        </div>
      </div>
      {clusters.length === 0 ? (
        <p className="text-[11px] text-muted-foreground text-center py-1">
          كل الترندات مخفية · اضغط "استعادة الكل" لإعادة عرضها
        </p>
      ) : (
      <div className="flex flex-wrap gap-1.5" dir="rtl">
        {clusters.map((c) => {
          const cfg = RISK_LEVEL_CONFIG[c.riskLevel];
          const isActive = activeTrend === c.trend;
          return (
            <div key={c.trend} className="group relative">
              <button
                onClick={() => onTrendClick(isActive ? null : c.trend)}
                className={`flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-xl font-medium transition-all border ${
                  isActive
                    ? `${cfg.bg} ${cfg.color} ${cfg.border} shadow-md scale-105`
                    : `bg-secondary/20 text-foreground/80 border-border/30 hover:bg-secondary/40 hover:scale-105`
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dot}`} />
                <Hash className="w-2.5 h-2.5 opacity-60" />
                <span>{c.trend}</span>
                <span className={`text-[9px] font-mono-data rounded-full px-1 ${
                  isActive ? 'bg-white/10' : 'bg-border/30 text-muted-foreground'
                }`}>
                  {c.postCount}
                </span>
                {c.flaggedCount > 0 && (
                  <span className="text-[9px] font-mono-data text-red-400">
                    ⚠{c.flaggedCount}
                  </span>
                )}
              </button>
              {/* Dismiss × — floats outside top-left corner on hover */}
              <button
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onHideTrend(c.trend);
                }}
                className="absolute -top-2 -left-2 w-4 h-4 rounded-full bg-background border border-border/60 text-muted-foreground hover:text-orange-400 hover:border-orange-500/60 hover:bg-orange-500/10 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center shadow-sm z-10"
                title="إخفاء مؤقت (يمكن الاستعادة)"
              >
                <X className="w-2.5 h-2.5" />
              </button>
              {/* Trash — floats outside top-right corner on hover, permanently deletes from backend */}
              <button
                onMouseDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onDeleteTrend(c.trend);
                }}
                className="absolute -top-2 -right-2 w-4 h-4 rounded-full bg-background border border-border/60 text-muted-foreground hover:text-red-500 hover:border-red-600/60 hover:bg-red-600/10 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center shadow-sm z-10"
                title="حذف نهائي من الخادم"
              >
                <Trash2 className="w-2.5 h-2.5" />
              </button>
            </div>
          );
        })}
      </div>
      )}
      {activeTrend && (
        <p className="text-[10px] text-primary/80 flex items-center gap-1">
          <TrendingUp className="w-3 h-3" />
          منشورات ترند #{activeTrend} · مرتبة حسب الأولوية
        </p>
      )}
    </div>
  );
}

// ── Pagination Bar ────────────────────────────────────────────────────────────

function PaginationBar({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  // Build the array of page numbers/ellipsis to show
  // Always show first, last, current ±1. Fill gaps with '…'
  const pages: (number | '…')[] = [];
  const addPage = (n: number) => {
    if (!pages.includes(n)) pages.push(n);
  };

  addPage(1);
  if (currentPage > 3) pages.push('…');
  for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) addPage(i);
  if (currentPage < totalPages - 2) pages.push('…');
  if (totalPages > 1) addPage(totalPages);

  return (
    <div className="flex items-center justify-center gap-1.5 pt-2 pb-1" dir="ltr">
      {/* Prev */}
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-border/40 bg-secondary/20 text-muted-foreground hover:text-foreground hover:bg-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        <ChevronLeft className="w-3 h-3" /> Prev
      </button>

      {/* Page pills */}
      {pages.map((p, i) =>
        p === '…' ? (
          <span key={`ellipsis-${i}`} className="px-1 text-xs text-muted-foreground select-none">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p as number)}
            className={`min-w-[30px] h-7 px-2 text-xs rounded-lg border transition-colors ${
              p === currentPage
                ? 'bg-primary/20 text-primary border-primary/40 font-semibold shadow-sm'
                : 'border-border/30 bg-secondary/10 text-muted-foreground hover:text-foreground hover:bg-secondary/40'
            }`}
          >
            {p}
          </button>
        )
      )}

      {/* Next */}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-border/40 bg-secondary/20 text-muted-foreground hover:text-foreground hover:bg-secondary/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >
        Next <ChevronRight className="w-3 h-3" />
      </button>
    </div>
  );
}

// ── Agent Status Panel ────────────────────────────────────────────────────────

const SOURCE_LABELS: Record<string, string> = {
  trend_search: 'Trend Search',
  public_keyword_search: 'Public Keywords',
  curated_queries: 'Curated Queries',
  authenticated_trend_search: 'Trend API',
  guest_api_keyword_scan: 'Guest API Scan',
  seed_query_search: 'Seed Queries',
};

function AgentStatusPanel({ status }: { status: HateSpeechAgentStatus }) {
  const isActive = status.isRunning;
  const nextScan = status.nextScanAt ? new Date(status.nextScanAt) : null;
  const lastScan = status.lastScanAt ? new Date(status.lastScanAt) : null;

  const nowMs = Date.now();
  const secsUntilNext = nextScan ? Math.max(0, Math.round((nextScan.getTime() - nowMs) / 1000)) : null;
  const nextLabel = secsUntilNext !== null
    ? secsUntilNext < 60 ? `${secsUntilNext}s` : `${Math.round(secsUntilNext / 60)}m`
    : '—';

  // Progress toward next scan: use actual last→next window when available
  let progressPct = 0;
  if (lastScan && nextScan) {
    const totalMs = nextScan.getTime() - lastScan.getTime();
    const elapsedMs = Date.now() - lastScan.getTime();
    progressPct = Math.max(0, Math.min(100, Math.round((elapsedMs / totalMs) * 100)));
  } else if (secsUntilNext !== null) {
    const cycleSecs = 300;
    progressPct = Math.max(0, Math.min(100, Math.round(((cycleSecs - secsUntilNext) / cycleSecs) * 100)));
  }

  const SOURCE_ICONS: Record<string, string> = {
    trend_search: '📈',
    public_keyword_search: '🔍',
    curated_queries: '📋',
    authenticated_trend_search: '🔐',
    guest_api_keyword_scan: '👁',
    seed_query_search: '🌱',
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-primary/5 via-background to-secondary/20">
      {/* Top accent bar */}
      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-primary/60 to-transparent" />

      {/* Animated scan line when active */}
      {isActive && (
        <div
          className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent"
          style={{ animation: 'scan-line 2s linear infinite', top: '20%' }}
        />
      )}

      <div className="p-4 space-y-3">
        {/* ── Header row ── */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            {/* Agent icon */}
            <div className={`relative flex items-center justify-center w-8 h-8 rounded-lg shrink-0 ${
              isActive ? 'bg-green-500/15 border border-green-500/30' : 'bg-primary/10 border border-primary/20'
            }`}>
              <Search className={`w-4 h-4 ${isActive ? 'text-green-400' : 'text-primary'}`} />
              {isActive && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-400 animate-ping" />
              )}
              {isActive && (
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-400" />
              )}
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-foreground tracking-tight">Public Discovery Agent</span>
                <span className={`text-[9px] px-2 py-0.5 rounded-full font-semibold border ${
                  isActive
                    ? 'bg-green-500/15 text-green-400 border-green-500/30'
                    : 'bg-primary/10 text-primary border-primary/20'
                }`}>
                  {isActive ? '⟳ Scanning…' : '✓ Active'}
                </span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">
                Searches <span className="text-foreground/80 font-medium">all public X posts</span> ·{' '}
                <span className="text-primary/80 font-medium">{status.queriesUsed} Arabic keyword queries</span> ·{' '}
                hate · incitement · Lebanon
              </p>
            </div>
          </div>

          {/* Scan count badge */}
          <div className="shrink-0 flex flex-col items-end gap-0.5">
            <span className="text-lg font-bold font-mono-data text-foreground leading-none">{status.scanCount}</span>
            <span className="text-[9px] text-muted-foreground uppercase tracking-wide">scans</span>
          </div>
        </div>

        {/* ── Stats grid ── */}
        <div className="grid grid-cols-3 gap-2">
          {/* Posts found */}
          <div className="flex flex-col gap-0.5 rounded-lg bg-secondary/30 border border-border/20 px-3 py-2">
            <span className="text-base font-bold font-mono-data text-blue-400 leading-none">{status.lastScanPostsFound}</span>
            <span className="text-[9px] text-muted-foreground">posts · last scan</span>
          </div>

          {/* Stored posts */}
          <div className="flex flex-col gap-0.5 rounded-lg bg-secondary/30 border border-border/20 px-3 py-2">
            <span className="text-base font-bold font-mono-data text-foreground leading-none">{status.currentPostsInStore}</span>
            <span className="text-[9px] text-muted-foreground">posts stored</span>
          </div>

          {/* Next scan */}
          <div className="flex flex-col gap-0.5 rounded-lg bg-primary/5 border border-primary/15 px-3 py-2">
            <span className="text-base font-bold font-mono-data text-primary leading-none">{nextLabel}</span>
            <span className="text-[9px] text-muted-foreground">until next scan</span>
          </div>
        </div>

        {/* ── Scan progress bar ── */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[9px] text-muted-foreground">
            <span className="uppercase tracking-wider">Scan Cycle</span>
            <span className="font-mono-data">{progressPct}%</span>
          </div>
          <div className="h-1 rounded-full bg-secondary/50 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary/60 to-primary transition-all duration-1000"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* ── Sources + last scan time ── */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          {/* Sources */}
          {status.sourcesLastScan.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[9px] text-muted-foreground uppercase tracking-wider shrink-0">Sources:</span>
              {status.sourcesLastScan.map((s) => (
                <span key={s} className="text-[9px] px-1.5 py-0.5 rounded-md bg-green-500/10 text-green-400 border border-green-500/20 font-medium flex items-center gap-0.5">
                  <span>{SOURCE_ICONS[s] ?? '·'}</span>
                  <span>{SOURCE_LABELS[s] ?? s}</span>
                </span>
              ))}
            </div>
          )}

          {/* Last scan time */}
          {lastScan && (
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground shrink-0 mr-auto">
              <Clock className="w-3 h-3" />
              <span>{formatDistanceToNow(lastScan, { addSuffix: true })}</span>
              {status.lastScanDurationSeconds > 0 && (
                <span className="font-mono-data text-muted-foreground/60">· {status.lastScanDurationSeconds}s</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom accent bar */}
      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
    </div>
  );
}

// ── Hashtag Search Panel ──────────────────────────────────────────────────────

function HashtagSearchPanel({
  onHashtagClick,
  onTrendClick,
  onReview,
  onOpenReplies,
  activeHashtag,
  activeTrend,
}: {
  onHashtagClick: (tag: string) => void;
  onTrendClick: (trend: string) => void;
  onReview: (id: string, action: 'confirmed' | 'dismissed') => void;
  onOpenReplies: (post: HateSpeechPost) => void;
  activeHashtag: string | null;
  activeTrend: string | null;
}) {
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<HateSpeechPost[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    const q = query.trim().replace(/^#+/, '');
    if (!q) return;
    setSearching(true);
    setError(null);
    setSearched(false);
    try {
      const data = await fetchHateSpeechSearch(q, 10);
      // Sort by engagement total (most interactions first)
      data.sort((a, b) => b.engagementTotal - a.engagementTotal);
      setResults(data);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') void handleSearch();
  };

  return (
    <div className="glass-panel border border-border/40 p-4 space-y-3">
      {/* Title */}
      <div className="flex items-center gap-2">
        <Search className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">بحث الهاشتاق المباشر</h3>
        <span className="text-[10px] text-muted-foreground">· بيانات X الحقيقية · أعلى 10 تفاعلاً</span>
      </div>

      {/* Input row */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          {/* # on the RIGHT side for RTL Arabic input */}
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm font-bold text-primary select-none">#</span>
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (!e.target.value.trim()) {
                setResults([]);
                setSearched(false);
                setError(null);
              }
            }}
            onKeyDown={handleKey}
            placeholder="مثال: لبنان  أو  طائفية_لبنان"
            dir="rtl"
            className="w-full pr-8 pl-3 py-2 text-sm rounded-lg bg-secondary/40 border border-border/50 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
          />
        </div>
        {/* Clear button — only visible when there is text */}
        {query && (
          <button
            onMouseDown={(e) => {
              e.preventDefault();
              setQuery('');
              setResults([]);
              setSearched(false);
              setError(null);
            }}
            className="flex items-center justify-center w-8 h-8 rounded-lg bg-secondary/50 border border-border/50 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors shrink-0"
            title="مسح البحث"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          onClick={() => void handleSearch()}
          disabled={searching || !query.trim()}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors shrink-0"
        >
          {searching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
          {searching ? 'جارٍ البحث…' : 'بحث'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="text-xs text-warning flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> {error}
        </div>
      )}

      {/* Results */}
      {searched && !searching && (
        <>
          <div className="flex items-center gap-2 pb-1 border-b border-border/30">
            <span className="text-[11px] text-muted-foreground" dir="rtl">
              {results.length === 0
                ? `لا توجد منشورات لـ #${query.replace(/^#/, '')}`
                : `${results.length} منشور الأكثر تفاعلاً لـ #${query.replace(/^#/, '')}`}
            </span>
            {results.length > 0 && (
              <span className="text-[10px] text-muted-foreground/60">· مرتبة حسب التفاعل</span>
            )}
          </div>
          {results.length > 0 && (
            <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
              {results.map((post) => (
                <PostCard
                  key={post.id}
                  post={post}
                  activeHashtag={activeHashtag}
                  activeTrend={activeTrend}
                  onReview={onReview}
                  onOpenReplies={onOpenReplies}
                  onHashtagClick={onHashtagClick}
                  onTrendClick={onTrendClick}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Mini stat ─────────────────────────────────────────────────────────────────

function MiniStat({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-2.5 rounded-xl bg-secondary/30 border border-border/40 min-w-[80px]">
      <span className={`text-xl font-bold font-mono-data ${color}`}>{value}</span>
      <span className="text-[10px] text-muted-foreground mt-0.5 text-center leading-tight">{label}</span>
    </div>
  );
}

// ── Side panel ────────────────────────────────────────────────────────────────

function SidePanel({
  stats,
  activeTrends,
  langPosts,
}: {
  stats: HateSpeechStats;
  activeTrends: HateSpeechTrendCluster[];
  langPosts: HateSpeechPost[];
}) {
  const catCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of langPosts) counts[p.category] = (counts[p.category] ?? 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [langPosts]);
  const total = langPosts.length || 1;

  // Top risky clusters
  const topRiskyClusters = useMemo(
    () => activeTrends.filter(c => c.flaggedCount > 0).slice(0, 5),
    [activeTrends],
  );

  return (
    <div className="space-y-4">
      {/* Risky trend clusters */}
      {topRiskyClusters.length > 0 && (
        <div className="glass-panel p-4 space-y-2">
          <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Flame className="w-3.5 h-3.5 text-rose-400" />
            ترندات عالية الخطورة
          </h3>
          <div className="space-y-2">
            {topRiskyClusters.map((c) => {
              const cfg = RISK_LEVEL_CONFIG[c.riskLevel];
              return (
                <div key={c.trend} className={`p-2 rounded-lg ${cfg.bg} border ${cfg.border}`}>
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <span className={`text-[10px] font-semibold ${cfg.color}`}>#{c.trend}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                      {cfg.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[9px] text-muted-foreground">
                    <span>{c.postCount} منشور</span>
                    <span className="text-red-400">⚠ {c.flaggedCount} مُبلَّغ</span>
                    <span className="ml-auto font-mono-data text-foreground/70">
                      {Math.round(c.maxRiskScore)}% max
                    </span>
                  </div>
                  {/* Flag rate bar */}
                  <div className="mt-1.5 h-1 rounded-full bg-border/40">
                    <div
                      className={`h-1 rounded-full ${cfg.dot}`}
                      style={{ width: `${Math.min(100, c.flagRate * 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Category breakdown */}
      <div className="glass-panel p-4 space-y-2">
        <h3 className="text-xs font-semibold text-foreground">تصنيف المنشورات</h3>
        <div className="space-y-1.5">
          {catCounts.map(([cat, count]) => {
            const cfg = CATEGORY_CONFIG[cat] ?? CATEGORY_CONFIG.general;
            const pct = Math.round((count / total) * 100);
            return (
              <div key={cat}>
                <div className="flex justify-between text-[10px] mb-0.5">
                  <span className={cfg.color}>{cfg.labelAr}</span>
                  <span className="text-muted-foreground font-mono-data">{count} ({pct}%)</span>
                </div>
                <div className="h-1 rounded-full bg-border/40">
                  <div
                    className={`h-1 rounded-full ${cfg.color.replace('text-', 'bg-')}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
          {catCounts.length === 0 && <p className="text-[10px] text-muted-foreground">لا توجد بيانات</p>}
        </div>
      </div>

      {/* Flagged accounts */}
      {stats.accountsFlagged.length > 0 && (
        <div className="glass-panel p-4 space-y-2">
          <h3 className="text-xs font-semibold text-foreground">حسابات مُبلَّغ عنها</h3>
          <div className="flex flex-wrap gap-1.5">
            {stats.accountsFlagged.map((h) => (
              <span key={h} className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-mono-data">
                @{h}
              </span>
            ))}
          </div>
        </div>
      )}

      {stats.lastScanAt && (
        <p className="text-[10px] text-muted-foreground text-center flex items-center justify-center gap-1">
          <Clock className="w-3 h-3" />
          آخر فحص {formatDistanceToNow(new Date(stats.lastScanAt), { addSuffix: true })}
        </p>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function HateSpeechMonitor() {
  const { incidents, alerts, stats: liveStats, lastUpdated, connectionStatus, acknowledgeAlert } = useLiveData(60000);

  const [hsStats, setHsStats] = useState<HateSpeechStats | null>(null);
  const [allPosts, setAllPosts] = useState<HateSpeechPost[]>([]);
  const [agentStatus, setAgentStatus] = useState<HateSpeechAgentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [langTab, setLangTab] = useState<LangTab>('ar');
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [sortBy, setSortBy] = useState<HateSpeechSortOption>('priority');
  const [activeHashtag, setActiveHashtag] = useState<string | null>(null);
  const [activeTrend, setActiveTrend] = useState<string | null>(null);
  const [hiddenTrends, setHiddenTrends] = useState<Set<string>>(new Set());
  const [selectedPost, setSelectedPost] = useState<HateSpeechPost | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const POSTS_PER_PAGE = 15;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, postsData, agentData] = await Promise.all([
        fetchHateSpeechStats(),
        fetchHateSpeechAllPosts({ hours: 24, limit: 200, sort: 'priority' }),
        fetchHateSpeechAgentStatus().catch(() => null),
      ]);
      setHsStats(statsData);
      setAllPosts(postsData);
      if (agentData) setAgentStatus(agentData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 60000);
    return () => clearInterval(interval);
  }, [load]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerHateSpeechScan();
      toast.success('تم تشغيل الفحص — ستظهر النتائج قريباً');
      setTimeout(() => void load(), 4000);
    } catch {
      toast.error('فشل الفحص — تحقق من السجلات');
    } finally {
      setScanning(false);
    }
  };

  const handleReview = async (id: string, action: 'confirmed' | 'dismissed') => {
    try {
      await reviewHateSpeechPost(id, action);
      toast.success(action === 'confirmed' ? 'تم تأكيده كخطاب كراهية' : 'تم تجاهله كإيجابي كاذب');
      setAllPosts((prev) => prev.map((p) => (p.id === id ? { ...p, reviewed: true, reviewAction: action } : p)));
    } catch {
      toast.error('فشلت عملية المراجعة');
    }
  };

  const handleHashtagSelect = (tag: string | null) => {
    setActiveHashtag(tag);
    setActiveTrend(null); // clear trend filter when hashtag selected
  };

  const handleTrendSelect = (trend: string | null) => {
    setActiveTrend(trend);
    setActiveHashtag(null); // clear hashtag filter when trend selected
  };

  const handleHideTrend = (trend: string) => {
    setHiddenTrends((prev) => new Set([...prev, trend]));
    if (activeTrend === trend) setActiveTrend(null);
  };

  const handleRestoreAllTrends = () => setHiddenTrends(new Set());

  const handleDeleteTrend = async (trend: string) => {
    // Hide it from the UI immediately so it disappears before the API call completes
    setHiddenTrends((prev) => new Set([...prev, trend]));
    if (activeTrend === trend) setActiveTrend(null);
    try {
      const result = await deleteHateSpeechTrend(trend);
      toast.success(`تم حذف ترند #${trend} نهائياً (${result.postsDeleted} منشور محذوف)`);
      // Reload the page data so the stats + clusters update immediately
      void load();
    } catch {
      toast.error(`فشل حذف ترند #${trend}`);
      // Undo the hide if the delete failed
      setHiddenTrends((prev) => { const s = new Set(prev); s.delete(trend); return s; });
    }
  };

  // Client-side sort (posts already sorted by priority from server, re-sort when user changes)
  const sortedPosts = useMemo(() => {
    const sorted = [...allPosts];
    if (sortBy === 'priority')   sorted.sort((a, b) => b.priorityScore - a.priorityScore);
    if (sortBy === 'velocity')   sorted.sort((a, b) => b.engagementVelocity - a.engagementVelocity);
    if (sortBy === 'score')      sorted.sort((a, b) => b.hateScore - a.hateScore);
    if (sortBy === 'engagement') sorted.sort((a, b) => b.engagementTotal - a.engagementTotal);
    if (sortBy === 'recent')     sorted.sort((a, b) => new Date(b.postedAt).getTime() - new Date(a.postedAt).getTime());
    return sorted;
  }, [allPosts, sortBy]);

  // Filtered posts
  const visiblePosts = useMemo(() => {
    let posts = langTab === 'all' ? sortedPosts : sortedPosts.filter((p) => p.language === langTab);

    // Hide posts whose trend has been dismissed
    if (hiddenTrends.size > 0) {
      posts = posts.filter((p) => !hiddenTrends.has(p.matchedTrend));
    }

    if (activeTrend) {
      posts = posts.filter((p) => p.matchedTrend.toLowerCase() === activeTrend.toLowerCase());
    } else if (activeHashtag) {
      const tag = activeHashtag.toLowerCase();
      posts = posts.filter((p) => p.hashtags.some((h) => h.toLowerCase() === tag));
      posts = posts.slice(0, 5); // top 5 for hashtag filter
    } else if (flaggedOnly) {
      posts = posts.filter((p) => p.isFlagged || p.hateScore >= 40);
    }

    return posts;
  }, [sortedPosts, langTab, flaggedOnly, activeHashtag, activeTrend, hiddenTrends]);

  // Reset to page 1 whenever the visible set changes
  useEffect(() => { setCurrentPage(1); }, [langTab, flaggedOnly, sortBy, activeHashtag, activeTrend, hiddenTrends]);

  // Pagination derived values
  const totalPages = Math.max(1, Math.ceil(visiblePosts.length / POSTS_PER_PAGE));
  const paginatedPosts = visiblePosts.slice((currentPage - 1) * POSTS_PER_PAGE, currentPage * POSTS_PER_PAGE);

  const langCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allPosts.length };
    for (const p of allPosts) counts[p.language] = (counts[p.language] ?? 0) + 1;
    return counts;
  }, [allPosts]);

  const arFlagged = allPosts.filter((p) => p.language === 'ar' && p.hateScore >= 40).length;
  const totalFlagged = hsStats?.totalFlagged ?? 0;
  const activeTrends = (hsStats?.activeTrends ?? []).filter((c) => !hiddenTrends.has(c.trend));

  return (
    <>
      <DashboardLayout liveData={{ incidents, alerts, stats: liveStats, lastUpdated, connectionStatus, acknowledgeAlert }}>
        <div className="space-y-5">

          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
                <ShieldAlert className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-foreground">مراقبة خطاب الكراهية</h1>
                <p className="text-[11px] text-muted-foreground">
                  وكيل اكتشاف عام · يفحص جميع المنشورات العامة · لبنان
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => void load()}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> تحديث
              </button>
              <button
                onClick={() => void handleScan()}
                disabled={scanning}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 disabled:opacity-50"
              >
                {scanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                {scanning ? 'جارٍ الفحص…' : 'فحص الآن'}
              </button>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="glass-panel border border-warning/30 p-3 text-xs text-warning flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}

          {/* Stats strip */}
          <div className="flex items-center gap-3 flex-wrap">
            <MiniStat label="إجمالي المجموعة" value={hsStats?.totalScraped ?? '—'} color="text-blue-400" />
            <MiniStat label="ترندات نشطة"     value={activeTrends.length}           color="text-primary" />
            <MiniStat label="مشبوه (عربي)"     value={arFlagged}                     color="text-yellow-400" />
            <MiniStat label="مُبلَّغ عنه"       value={totalFlagged}                  color="text-red-400" />
            <MiniStat label="آخر ساعة"         value={hsStats?.flaggedLast1h ?? 0}   color="text-orange-400" />
          </div>

          {/* Agent status panel */}
          {agentStatus && <AgentStatusPanel status={agentStatus} />}

          {/* Trend cluster chips */}
          <TrendClusterPanel
            clusters={activeTrends}
            activeTrend={activeTrend}
            onTrendClick={handleTrendSelect}
            onHideTrend={handleHideTrend}
            hiddenCount={hiddenTrends.size}
            onRestoreAll={handleRestoreAllTrends}
            onDeleteTrend={handleDeleteTrend}
          />

          {/* Hashtag search */}
          <HashtagSearchPanel
            onHashtagClick={handleHashtagSelect}
            onTrendClick={handleTrendSelect}
            onReview={handleReview}
            onOpenReplies={setSelectedPost}
            activeHashtag={activeHashtag}
            activeTrend={activeTrend}
          />

          {/* Main 2-col layout */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-5">

            {/* Left — feed */}
            <div className="space-y-3 min-w-0">

              {/* Lang tabs + sort + filter row */}
              <div className="flex items-center gap-2 flex-wrap">
                {/* Language tabs */}
                <div className="flex rounded-xl border border-border/50 p-0.5 bg-secondary/20">
                  {LANG_TABS.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setLangTab(tab.key)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                        langTab === tab.key
                          ? 'bg-primary/15 text-primary shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      <span>{tab.flag}</span>
                      <span>{tab.label}</span>
                      <span className={`text-[10px] font-mono-data rounded-full px-1.5 py-0.5 ${
                        langTab === tab.key ? 'bg-primary/20 text-primary' : 'bg-border/50 text-muted-foreground'
                      }`}>
                        {tab.key === 'all' ? allPosts.length : (langCounts[tab.key] ?? 0)}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Sort buttons */}
                <div className="flex rounded-xl border border-border/50 p-0.5 bg-secondary/20">
                  {SORT_OPTIONS.map((opt) => {
                    const Icon = opt.icon;
                    return (
                      <button
                        key={opt.key}
                        onClick={() => setSortBy(opt.key)}
                        title={opt.label}
                        className={`flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg transition-colors ${
                          sortBy === opt.key
                            ? 'bg-primary/15 text-primary shadow-sm'
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        <Icon className="w-3 h-3" />
                        <span className="hidden sm:inline">{opt.labelAr}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Flagged filter (only when no trend/hashtag active) */}
                {!activeHashtag && !activeTrend && (
                  <button
                    onClick={() => setFlaggedOnly(!flaggedOnly)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                      flaggedOnly
                        ? 'bg-red-500/15 text-red-400 border-red-500/30'
                        : 'bg-secondary/30 text-muted-foreground border-border/40 hover:text-foreground'
                    }`}
                  >
                    <ShieldAlert className="w-3.5 h-3.5" />
                    {flaggedOnly ? 'مشبوه فقط' : 'الكل'}
                  </button>
                )}

                <span className="ml-auto text-[10px] text-muted-foreground font-mono-data">
                  {activeTrend
                    ? `ترند #${activeTrend} · ${visiblePosts.length} منشور`
                    : activeHashtag
                    ? `أعلى 5 · #${activeHashtag}`
                    : visiblePosts.length > 0
                    ? `${(currentPage - 1) * POSTS_PER_PAGE + 1}–${Math.min(currentPage * POSTS_PER_PAGE, visiblePosts.length)} من ${visiblePosts.length} منشور`
                    : '0 منشور'
                  }
                </span>
              </div>

              {/* Post list */}
              {loading ? (
                <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm">جارٍ تحميل الترندات…</span>
                </div>
              ) : visiblePosts.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground">
                  <ShieldAlert className="w-8 h-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">
                    {activeTrend
                      ? `لا توجد منشورات لترند #${activeTrend}`
                      : activeHashtag
                      ? `لا توجد منشورات بهاشتاق #${activeHashtag}`
                      : 'لا توجد منشورات — شغّل فحصاً للبدء'}
                  </p>
                </div>
              ) : (
                <>
                  <div className="space-y-2.5">
                    {paginatedPosts.map((post) => (
                      <PostCard
                        key={post.id}
                        post={post}
                        activeHashtag={activeHashtag}
                        activeTrend={activeTrend}
                        onReview={handleReview}
                        onOpenReplies={setSelectedPost}
                        onHashtagClick={handleHashtagSelect}
                        onTrendClick={handleTrendSelect}
                      />
                    ))}
                  </div>

                  {/* Pagination controls */}
                  {totalPages > 1 && (
                    <PaginationBar
                      currentPage={currentPage}
                      totalPages={totalPages}
                      onPageChange={setCurrentPage}
                    />
                  )}
                </>
              )}
            </div>

            {/* Right — side panel */}
            <div className="hidden lg:block">
              <div className="sticky top-20">
                {hsStats ? (
                  <SidePanel
                    stats={hsStats}
                    activeTrends={activeTrends}
                    langPosts={langTab === 'all' ? allPosts : allPosts.filter((p) => p.language === langTab)}
                  />
                ) : (
                  <div className="glass-panel p-4 text-center text-xs text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin mx-auto mb-2" />
                    جارٍ التحميل…
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </DashboardLayout>

      {/* Replies modal */}
      {selectedPost && (
        <RepliesModal
          post={selectedPost}
          onClose={() => setSelectedPost(null)}
        />
      )}
    </>
  );
}
