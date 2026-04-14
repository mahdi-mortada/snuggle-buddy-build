import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useLiveData } from '@/hooks/useLiveData';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { formatDistanceToNow } from 'date-fns';
import {
  ShieldAlert, AlertTriangle, RefreshCw, XCircle, Hash, Clock,
  TrendingUp, Zap, ExternalLink, MessageSquare, Heart, Repeat2,
  ChevronDown, ChevronUp, X, Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  fetchHateSpeechStats,
  fetchHateSpeechAllPosts,
  triggerHateSpeechScan,
  reviewHateSpeechPost,
  fetchHateSpeechReplies,
  type HateSpeechPost,
  type HateSpeechStats,
  type HateSpeechReply,
} from '@/services/backendApi';

// ── Config ─────────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; labelAr: string; color: string; bg: string }> = {
  sectarian:        { label: 'Sectarian',       labelAr: 'طائفي',        color: 'text-red-400',    bg: 'bg-red-500/10' },
  anti_refugee:     { label: 'Anti-Refugee',    labelAr: 'ضد اللاجئين',  color: 'text-orange-400', bg: 'bg-orange-500/10' },
  political_incite: { label: 'Political Incite',labelAr: 'تحريض سياسي', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  misogynistic:     { label: 'Misogynistic',    labelAr: 'كراهية المرأة',color: 'text-purple-400', bg: 'bg-purple-500/10' },
  general:          { label: 'General Hate',    labelAr: 'كراهية عامة',  color: 'text-pink-400',   bg: 'bg-pink-500/10' },
  clean:            { label: 'Clean',           labelAr: 'نظيف',         color: 'text-green-400',  bg: 'bg-green-500/10' },
};

const LANG_TABS = [
  { key: 'ar', label: 'العربية', flag: '🇱🇧' },
  { key: 'en', label: 'English', flag: '🇬🇧' },
  { key: 'fr', label: 'Français', flag: '🇫🇷' },
  { key: 'all', label: 'All', flag: '🌐' },
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

function RepliesModal({
  post,
  onClose,
}: {
  post: HateSpeechPost;
  onClose: () => void;
}) {
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

  // Close on overlay click
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={handleOverlayClick}
    >
      <div className="glass-panel w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden border border-border/60 shadow-2xl">
        {/* Modal header */}
        <div className="flex items-start gap-3 p-4 border-b border-border/40 shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-foreground">@{post.authorHandle}</span>
              <span className="text-[10px] text-muted-foreground">·</span>
              <span className="text-[10px] text-muted-foreground">
                {formatDistanceToNow(new Date(post.postedAt), { addSuffix: true })}
              </span>
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
              lang={post.language}
            >
              {post.content}
            </p>
            {/* Engagement summary */}
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
          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-lg hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Replies list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5 sticky top-0 bg-transparent">
            <MessageSquare className="w-3.5 h-3.5 text-primary" />
            أكثر التعليقات تفاعلاً
          </h3>

          {loading && (
            <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              جارٍ تحميل التعليقات…
            </div>
          )}

          {error && !loading && (
            <div className="text-center py-8 text-muted-foreground text-xs">
              <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-warning" />
              {error}
              <p className="mt-1 text-[10px]">قد تكون التعليقات غير متاحة لهذا المنشور</p>
            </div>
          )}

          {!loading && !error && replies.length === 0 && (
            <div className="text-center py-10 text-muted-foreground text-xs">
              <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-40" />
              لا توجد تعليقات متاحة
            </div>
          )}

          {!loading && replies.map((reply, idx) => {
            const replyIsAr = reply.language === 'ar';
            return (
              <div
                key={reply.id}
                className="glass-panel border border-border/30 p-3 space-y-2 hover:border-border/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-foreground/80">#{idx + 1}</span>
                  <span className="text-xs font-semibold text-foreground">@{reply.authorHandle}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground">
                    {formatDistanceToNow(new Date(reply.postedAt), { addSuffix: true })}
                  </span>
                </div>
                <p
                  className={`text-sm leading-relaxed text-foreground/90 ${replyIsAr ? 'text-right' : ''}`}
                  dir={replyIsAr ? 'rtl' : 'ltr'}
                  lang={reply.language}
                >
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
                    <a
                      href={reply.sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary flex items-center gap-0.5 hover:underline ml-auto"
                    >
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
  onReview,
  onOpenReplies,
  onHashtagClick,
}: {
  post: HateSpeechPost;
  activeHashtag: string | null;
  onReview: (id: string, action: 'confirmed' | 'dismissed') => void;
  onOpenReplies: (post: HateSpeechPost) => void;
  onHashtagClick: (tag: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const catCfg = CATEGORY_CONFIG[post.category] ?? CATEGORY_CONFIG.general;
  const isAr = post.language === 'ar';

  return (
    <div
      className={`glass-panel border overflow-hidden transition-all duration-200 ${
        post.reviewed ? 'opacity-50' : ''
      } ${
        activeHashtag && post.hashtags.includes(activeHashtag.toLowerCase())
          ? 'border-primary/50 shadow-[0_0_0_1px_rgba(var(--primary),0.2)]'
          : 'border-border/40 hover:border-border/70'
      }`}
    >
      {/* Clickable header — opens replies modal */}
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

            {/* Engagement + hashtags row */}
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
                  <MessageSquare className="w-3 h-3" /> {post.replyCount.toLocaleString()} تعليق
                </span>
              )}
              {/* Inline hashtag chips */}
              {post.hashtags.slice(0, 4).map((tag) => (
                <span
                  key={tag}
                  onClick={(e) => { e.stopPropagation(); onHashtagClick(tag); }}
                  className={`text-[10px] px-1.5 py-0.5 rounded-full cursor-pointer font-mono-data transition-colors ${
                    activeHashtag === tag
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20'
                  }`}
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          {/* Expand toggle for review actions */}
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            className="shrink-0 p-1 text-muted-foreground hover:text-foreground transition-colors mt-1"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </button>

      {/* Expanded actions */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-border/20 pt-3 flex items-center gap-2 flex-wrap">
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
                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
              >
                <AlertTriangle className="w-3 h-3" /> تأكيد كخطاب كراهية
              </button>
              <button
                onClick={() => onReview(post.id, 'dismissed')}
                className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
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

// ── Mini stat ─────────────────────────────────────────────────────────────────

function MiniStat({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-2.5 rounded-xl bg-secondary/30 border border-border/40 min-w-[80px]">
      <span className={`text-xl font-bold font-mono-data ${color}`}>{value}</span>
      <span className="text-[10px] text-muted-foreground mt-0.5 text-center leading-tight">{label}</span>
    </div>
  );
}

// ── Hashtag chips bar ─────────────────────────────────────────────────────────

function HashtagBar({
  hashtags,
  hashtagTopPosts,
  allPosts,
  activeHashtag,
  onSelect,
}: {
  hashtags: string[];
  hashtagTopPosts: Record<string, string[]>;
  allPosts: HateSpeechPost[];
  activeHashtag: string | null;
  onSelect: (tag: string | null) => void;
}) {
  if (hashtags.length === 0) return null;

  // Count posts per hashtag from local data
  const localCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of allPosts) {
      for (const t of p.hashtags) {
        counts[t] = (counts[t] ?? 0) + 1;
      }
    }
    return counts;
  }, [allPosts]);

  return (
    <div className="glass-panel p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <TrendingUp className="w-3.5 h-3.5 text-primary" />
          الهاشتاقات الرائجة في لبنان
          <span className="text-[10px] text-muted-foreground font-normal">· اضغط للتصفية</span>
        </h3>
        {activeHashtag && (
          <button
            onClick={() => onSelect(null)}
            className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            <X className="w-3 h-3" /> إلغاء التصفية
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5" dir="rtl">
        {hashtags.map((tag) => {
          const count = localCounts[tag.toLowerCase()] ?? localCounts[tag] ?? 0;
          const topCount = hashtagTopPosts[tag]?.length ?? 0;
          const isActive = activeHashtag === tag;
          return (
            <button
              key={tag}
              onClick={() => onSelect(isActive ? null : tag)}
              className={`flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full font-medium transition-all ${
                isActive
                  ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20 scale-105'
                  : 'bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 hover:scale-105'
              }`}
            >
              <Hash className="w-2.5 h-2.5" />
              {tag}
              {count > 0 && (
                <span className={`text-[9px] font-mono-data rounded-full px-1 ${
                  isActive ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-primary/20 text-primary'
                }`}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {activeHashtag && (
        <p className="text-[10px] text-primary/80 flex items-center gap-1">
          <Hash className="w-3 h-3" />
          عرض منشورات #{activeHashtag} · أعلى 5 بالتفاعل
        </p>
      )}
    </div>
  );
}

// ── Side panel ────────────────────────────────────────────────────────────────

function SidePanel({
  stats,
  langPosts,
}: {
  stats: HateSpeechStats;
  langPosts: HateSpeechPost[];
}) {
  const catCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of langPosts) counts[p.category] = (counts[p.category] ?? 0) + 1;
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [langPosts]);
  const total = langPosts.length || 1;

  const topEngaged = useMemo(
    () => [...langPosts].sort((a, b) => b.engagementTotal - a.engagementTotal).slice(0, 5),
    [langPosts],
  );

  return (
    <div className="space-y-4">
      {/* Top engaged posts */}
      {topEngaged.length > 0 && topEngaged[0].engagementTotal > 0 && (
        <div className="glass-panel p-4 space-y-2">
          <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-yellow-400" />
            الأكثر تفاعلاً
          </h3>
          <div className="space-y-2.5">
            {topEngaged.map((p) => (
              <div key={p.id} className="space-y-0.5">
                <div className="flex items-center justify-between gap-1">
                  <span className="text-[10px] text-muted-foreground font-mono-data">@{p.authorHandle}</span>
                  <span className="text-[10px] text-yellow-400 font-mono-data flex items-center gap-0.5">
                    <Heart className="w-2.5 h-2.5" />{p.likeCount.toLocaleString()}
                  </span>
                </div>
                <p
                  className="text-[10px] text-foreground/80 line-clamp-2"
                  dir={p.language === 'ar' ? 'rtl' : 'ltr'}
                >
                  {p.content}
                </p>
              </div>
            ))}
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
              <span
                key={h}
                className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20 font-mono-data"
              >
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
  const { incidents, alerts, stats: liveStats, lastUpdated, connectionStatus } = useLiveData(60000);

  const [hsStats, setHsStats] = useState<HateSpeechStats | null>(null);
  const [allPosts, setAllPosts] = useState<HateSpeechPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [langTab, setLangTab] = useState<LangTab>('ar');
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [activeHashtag, setActiveHashtag] = useState<string | null>(null);
  const [selectedPost, setSelectedPost] = useState<HateSpeechPost | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [statsData, postsData] = await Promise.all([
        fetchHateSpeechStats(),
        fetchHateSpeechAllPosts({ hours: 24, limit: 200 }),
      ]);
      setHsStats(statsData);
      setAllPosts(postsData);
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
      setTimeout(() => void load(), 3000);
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
      setAllPosts((prev) =>
        prev.map((p) => (p.id === id ? { ...p, reviewed: true, reviewAction: action } : p)),
      );
    } catch {
      toast.error('فشلت عملية المراجعة');
    }
  };

  const handleHashtagSelect = (tag: string | null) => {
    setActiveHashtag((prev) => (prev === tag ? null : tag));
  };

  // Filtered posts
  const visiblePosts = useMemo(() => {
    let posts = langTab === 'all' ? allPosts : allPosts.filter((p) => p.language === langTab);

    if (activeHashtag) {
      const tag = activeHashtag.toLowerCase();
      // Filter to posts containing this hashtag, take top 5 by engagement
      posts = posts.filter((p) => p.hashtags.some((h) => h.toLowerCase() === tag));
      posts = posts.sort((a, b) => b.engagementTotal - a.engagementTotal).slice(0, 5);
    } else {
      if (flaggedOnly) posts = posts.filter((p) => p.isFlagged || p.hateScore >= 40);
      // Sort by engagement
      posts = [...posts].sort((a, b) => b.engagementTotal - a.engagementTotal);
    }

    return posts;
  }, [allPosts, langTab, flaggedOnly, activeHashtag]);

  // Language tab counts
  const langCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allPosts.length };
    for (const p of allPosts) counts[p.language] = (counts[p.language] ?? 0) + 1;
    return counts;
  }, [allPosts]);

  const arFlagged = allPosts.filter((p) => p.language === 'ar' && p.hateScore >= 40).length;
  const totalFlagged = hsStats?.totalFlagged ?? 0;

  return (
    <>
      <DashboardLayout liveData={{ incidents, alerts, stats: liveStats, lastUpdated, connectionStatus }}>
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
                  Hate Speech Monitor · الهاشتاقات الرائجة على X · لبنان
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => void load()}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary/50 text-foreground border border-border/50 hover:bg-secondary transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> تحديث
              </button>
              <button
                onClick={() => void handleScan()}
                disabled={scanning}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors disabled:opacity-50"
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
            <MiniStat label="عربي" value={langCounts['ar'] ?? 0} color="text-primary" />
            <MiniStat label="مشبوه (عربي)" value={arFlagged} color="text-yellow-400" />
            <MiniStat label="مُبلَّغ عنه" value={totalFlagged} color="text-red-400" />
            <MiniStat label="آخر ساعة" value={hsStats?.flaggedLast1h ?? 0} color="text-orange-400" />
          </div>

          {/* Trending hashtag chips */}
          {hsStats && (
            <HashtagBar
              hashtags={hsStats.trendingHashtags}
              hashtagTopPosts={hsStats.hashtagTopPosts}
              allPosts={allPosts}
              activeHashtag={activeHashtag}
              onSelect={handleHashtagSelect}
            />
          )}

          {/* Main 2-col layout */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-5">

            {/* Left — feed */}
            <div className="space-y-3 min-w-0">

              {/* Language tabs + filter row */}
              <div className="flex items-center gap-2 flex-wrap">
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

                {!activeHashtag && (
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
                  {activeHashtag
                    ? `أعلى 5 منشورات · #${activeHashtag}`
                    : `${visiblePosts.length} منشور`
                  }
                </span>
              </div>

              {/* Post list */}
              {loading ? (
                <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span className="text-sm">جارٍ التحميل…</span>
                </div>
              ) : visiblePosts.length === 0 ? (
                <div className="text-center py-16 text-muted-foreground">
                  <ShieldAlert className="w-8 h-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">
                    {activeHashtag
                      ? `لا توجد منشورات بهاشتاق #${activeHashtag}`
                      : 'لا توجد منشورات — شغّل فحصاً للبدء'}
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  {visiblePosts.map((post) => (
                    <PostCard
                      key={post.id}
                      post={post}
                      activeHashtag={activeHashtag}
                      onReview={handleReview}
                      onOpenReplies={setSelectedPost}
                      onHashtagClick={(tag) => handleHashtagSelect(tag)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Right — side panel */}
            <div className="hidden lg:block">
              <div className="sticky top-20">
                {hsStats ? (
                  <SidePanel
                    stats={hsStats}
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
