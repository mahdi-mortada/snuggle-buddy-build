import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { OfficialFeedFilterPanel } from '@/components/official-feeds/OfficialFeedFilterPanelV2';
import { CredibilityBadge, SourceTag } from '@/components/shared/SourceBadge';
import { Badge } from '@/components/ui/badge';
import { useLiveData } from '@/hooks/useLiveData';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { openSourceUrl, resolveSourceUrl } from '@/lib/sourceLink';
import { buildLebanonLocationIndex, type LebanonLocationIndex, type OSMRawData } from '@/lib/lebanonLocations';
import {
  buildRegionOptions,
  filterOfficialFeedPosts,
  groupOfficialFeedPostsByPublisher,
  prepareOfficialFeedPosts,
} from '@/lib/officialFeedFilters';
import {
  createBackendOfficialFeedSource,
  deleteBackendOfficialFeedSource,
  fetchBackendOfficialFeedPosts,
  fetchBackendOfficialFeedSources,
} from '@/services/backendApi';
import type { OfficialFeedPost, OfficialFeedSource } from '@/types/crisis';
import { formatDistanceToNow } from 'date-fns';
import { ExternalLink, RefreshCw, Radio, Send } from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { toast } from 'sonner';

function platformLabel(platform: OfficialFeedPost['platform']): string {
  return platform === 'telegram' ? 'Telegram' : 'X';
}

export default function OfficialFeeds() {
  const { incidents, alerts, stats, lastUpdated, connectionStatus } = useLiveData(30000);
  const [posts, setPosts] = useState<OfficialFeedPost[]>([]);
  const [sources, setSources] = useState<OfficialFeedSource[]>([]);
  const [locationIndex, setLocationIndex] = useState<LebanonLocationIndex | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAddingSource, setIsAddingSource] = useState(false);
  const [deletingSourceIds, setDeletingSourceIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [selectedRegionIds, setSelectedRegionIds] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState('');
  const debouncedKeyword = useDebouncedValue(keywordInput, 250);

  const loadFeedData = async (showToast = false) => {
    setIsLoading(true);
    setError(null);
    try {
      const [nextPosts, nextSources] = await Promise.all([
        fetchBackendOfficialFeedPosts(24),
        fetchBackendOfficialFeedSources(),
      ]);
      setPosts(nextPosts);
      setSources(sortSources(nextSources));
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
    void loadFeedData();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadFeedData();
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let isMounted = true;

    fetch('/maps/osm-export.geojson')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Unable to load Lebanon regions (${response.status})`);
        }
        return response.json() as Promise<OSMRawData>;
      })
      .then((raw) => {
        if (!isMounted) return;
        setLocationIndex(buildLebanonLocationIndex(raw));
      })
      .catch((geoJsonError) => {
        console.error('Unable to build Lebanon location index:', geoJsonError);
        if (!isMounted) return;
        setLocationIndex(null);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Keep the raw backend payload as the single source of truth and derive
  // searchable metadata from it instead of duplicating another feed store.
  const preparedPosts = useMemo(() => prepareOfficialFeedPosts(posts, locationIndex), [posts, locationIndex]);
  const regionOptions = useMemo(() => buildRegionOptions(preparedPosts), [preparedPosts]);
  const filteredPosts = useMemo(
    () =>
      filterOfficialFeedPosts(preparedPosts, {
        selectedSources,
        selectedRegionIds,
        keyword: debouncedKeyword,
      }),
    [preparedPosts, selectedSources, selectedRegionIds, debouncedKeyword],
  );
  const groupedPosts = useMemo(() => groupOfficialFeedPostsByPublisher(filteredPosts), [filteredPosts]);

  const publishers = Object.keys(groupedPosts).length;
  const telegramCount = posts.filter((post) => post.platform === 'telegram').length;
  const filteredCount = filteredPosts.length;
  const clearFilters = () => {
    setSelectedSources([]);
    setSelectedRegionIds([]);
    setKeywordInput('');
  };

  const handleAddSource = async (input: string): Promise<boolean> => {
    const normalizedInput = input.trim();
    if (!normalizedInput) {
      toast.error('Enter a Telegram username or channel link first.');
      return false;
    }

    setIsAddingSource(true);
    try {
      const createdSource = await createBackendOfficialFeedSource(normalizedInput);
      setSources((currentSources) => sortSources(upsertSource(currentSources, createdSource)));
      toast.success(`Source added: @${createdSource.username}`);
      void loadFeedData();
      return true;
    } catch (addError) {
      const message = addError instanceof Error ? addError.message : 'Unable to add Telegram source.';
      toast.error(message);
      return false;
    } finally {
      setIsAddingSource(false);
    }
  };

  const handleDeleteSource = async (source: OfficialFeedSource): Promise<boolean> => {
    setDeletingSourceIds((currentIds) => (currentIds.includes(source.id) ? currentIds : [...currentIds, source.id]));
    try {
      await deleteBackendOfficialFeedSource(source.id);
      setSources((currentSources) => currentSources.filter((currentSource) => currentSource.id !== source.id));
      setSelectedSources((currentSelected) => currentSelected.filter((selectedSourceId) => selectedSourceId !== source.id));
      setPosts((currentPosts) => currentPosts.filter((post) => post.sourceId !== source.id));
      toast.success(`Source removed: @${source.username}`);
      void loadFeedData();
      return true;
    } catch (deleteError) {
      const message = deleteError instanceof Error ? deleteError.message : 'Unable to delete Telegram source.';
      toast.error(message);
      return false;
    } finally {
      setDeletingSourceIds((currentIds) => currentIds.filter((currentId) => currentId !== source.id));
    }
  };

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
                A separate stream for posts coming directly from the Telegram or mirrored social accounts of the TV and news outlets we trust.
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              void loadFeedData(true);
            }}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/10 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Feeds
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="glass-panel border border-border/50 p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Loaded Posts</div>
            <div className="mt-2 text-3xl font-bold text-foreground">{posts.length}</div>
            <div className="mt-1 text-xs text-muted-foreground">Most recent direct outlet posts available right now.</div>
          </div>
          <div className="glass-panel border border-border/50 p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Covered Publishers</div>
            <div className="mt-2 text-3xl font-bold text-foreground">{publishers}</div>
            <div className="mt-1 text-xs text-muted-foreground">Separate from the broader live news incident feed.</div>
          </div>
          <div className="glass-panel border border-border/50 p-4">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Telegram Posts</div>
            <div className="mt-2 text-3xl font-bold text-foreground">{telegramCount}</div>
            <div className="mt-1 text-xs text-muted-foreground">X-ready later, but currently ingested through public Telegram channels and mirrors.</div>
          </div>
        </div>

        <OfficialFeedFilterPanel
          sources={sources}
          regionOptions={regionOptions}
          selectedSources={selectedSources}
          selectedRegionIds={selectedRegionIds}
          keyword={keywordInput}
          totalResults={posts.length}
          filteredResults={filteredCount}
          regionOptionsReady={locationIndex !== null}
          isAddingSource={isAddingSource}
          deletingSourceIds={deletingSourceIds}
          onAddSource={handleAddSource}
          onDeleteSource={handleDeleteSource}
          onSourceChange={setSelectedSources}
          onRegionChange={setSelectedRegionIds}
          onKeywordChange={setKeywordInput}
          onClearFilters={clearFilters}
        />

        {error ? <div className="glass-panel border border-critical/30 p-5 text-sm text-critical">{error}</div> : null}

        {posts.length === 0 && !isLoading && !error ? (
          <div className="glass-panel border border-border/50 p-6 text-sm text-muted-foreground">
            No official outlet posts are available yet. Try refreshing in a moment.
          </div>
        ) : null}

        {posts.length > 0 && filteredCount === 0 && !isLoading && !error ? (
          <div className="glass-panel border border-border/50 p-6 text-sm text-muted-foreground">
            No posts match the current filters. Try changing the source, Lebanon location, or keyword criteria.
          </div>
        ) : null}

        <div className="space-y-6">
          {Object.entries(groupedPosts).map(([publisherName, publisherPosts]) => (
            <section key={publisherName} className="space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-foreground">{publisherName}</h2>
                <span className="rounded-full bg-secondary/60 px-2 py-1 text-[11px] text-muted-foreground">{publisherPosts.length} posts</span>
              </div>

              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                {publisherPosts.map((preparedPost) => {
                  const { post, matchedRegions } = preparedPost;
                  const sourceUrl = resolveSourceUrl(post);

                  return (
                    <article key={post.id} className="glass-panel border border-border/50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <SourceTag source={post.sourceInfo} clickable={false} />
                            <CredibilityBadge credibility={post.sourceInfo.credibility} score={post.sourceInfo.credibilityScore} />
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
                              <Send className="h-3.5 w-3.5" />@{post.accountHandle}
                            </a>
                            <span className="text-muted-foreground/40">-</span>
                            <span>{formatDistanceToNow(new Date(post.publishedAt), { addSuffix: true })}</span>
                          </div>
                        </div>
                        {sourceUrl ? (
                          <button
                            type="button"
                            onClick={() => openSourceUrl(sourceUrl)}
                            className="inline-flex items-center gap-1 rounded-lg border border-primary/20 bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/20"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            View Source
                          </button>
                        ) : null}
                      </div>

                      <p className="mt-4 whitespace-pre-line text-sm leading-6 text-foreground/85">
                        {renderHighlightedText(post.content, debouncedKeyword)}
                      </p>

                      {matchedRegions.length > 0 ? (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {matchedRegions.slice(0, 4).map((region) => (
                            <Badge
                              key={`${post.id}-region-${region.id}`}
                              variant="outline"
                              className="border-primary/20 bg-primary/5 text-[11px] text-primary/90"
                            >
                              {region.label}
                            </Badge>
                          ))}
                        </div>
                      ) : null}

                      {post.primaryKeyword ? (
                        <div className="mt-4 flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
                            Primary match: {post.primaryKeyword}
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            {post.matchedKeywords?.length ?? 0} configured keyword matches
                          </span>
                        </div>
                      ) : null}

                      {post.matchedKeywords && post.matchedKeywords.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {post.matchedKeywords.map((keyword) => (
                            <span
                              key={`${post.id}-matched-${keyword}`}
                              className="rounded-full border border-primary/25 bg-primary/5 px-2 py-1 text-[11px] text-primary/90"
                            >
                              match:{keyword}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      {post.signalTags.length > 0 ? (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {post.signalTags.map((tag) => (
                            <span key={`${post.id}-${tag}`} className="rounded-full border border-border/40 bg-accent/40 px-2 py-1 text-[11px] text-muted-foreground">
                              #{tag}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}

function renderHighlightedText(text: string, keyword: string): ReactNode {
  const trimmedKeyword = keyword.trim();
  if (!trimmedKeyword) {
    return text;
  }

  const matcher = new RegExp(`(${escapeRegExp(trimmedKeyword)})`, 'gi');
  return text.split(matcher).map((part, index) => {
    if (part.toLowerCase() === trimmedKeyword.toLowerCase()) {
      return (
        <mark key={`${part}-${index}`} className="rounded bg-warning/20 px-1 text-foreground">
          {part}
        </mark>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function sortSources(sources: OfficialFeedSource[]): OfficialFeedSource[] {
  return [...sources].sort((left, right) => {
    if (left.isActive !== right.isActive) {
      return left.isActive ? -1 : 1;
    }
    const nameComparison = left.name.localeCompare(right.name);
    if (nameComparison !== 0) {
      return nameComparison;
    }
    return left.username.localeCompare(right.username);
  });
}

function upsertSource(sources: OfficialFeedSource[], nextSource: OfficialFeedSource): OfficialFeedSource[] {
  const remainingSources = sources.filter((source) => source.id !== nextSource.id);
  return [...remainingSources, nextSource];
}
