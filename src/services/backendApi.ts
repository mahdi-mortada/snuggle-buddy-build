import { runtimeConfig } from "@/lib/runtimeConfig";
import type {
  Alert,
  CredibilityLevel,
  DashboardStats,
  Incident,
  OfficialFeedPost,
  OfficialFeedSource,
  RiskScore,
  SourceInfo,
  TrendDataPoint,
} from "@/types/crisis";

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  error: string | null;
};

type BackendSourceInfo = {
  name: string;
  type: string;
  credibility: string;
  credibilityScore: number;
  logoInitials: string;
  url?: string;
  verifiedBy?: string[];
};

type BackendIncident = {
  id: string;
  source: string;
  title: string;
  description: string;
  category: string;
  severity: string;
  location: { lat: number; lng: number };
  location_name: string;
  region: string;
  sentiment_score: number;
  risk_score: number;
  entities: string[];
  keywords: string[];
  status: string;
  source_info: BackendSourceInfo;
  source_url?: string;
  created_at: string;
};

type BackendRiskScore = {
  region: string;
  overall_score: number;
  sentiment_component: number;
  volume_component: number;
  keyword_component: number;
  behavior_component: number;
  geospatial_component: number;
  confidence: number;
  calculated_at: string;
};

type BackendAlert = {
  id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  recommendation: string;
  region: string;
  is_acknowledged: boolean;
  created_at: string;
  linked_incidents: string[];
};

type BackendTrendPoint = {
  time: string;
  incidents: number;
  risk_score: number;
  sentiment: number;
};

type BackendOverview = {
  total_incidents_24h: number;
  active_alerts: number;
  avg_risk_score: number;
  top_risk_region: string;
};

type BackendOfficialFeedPost = {
  id: string;
  source_id: string;
  is_custom: boolean;
  platform: string;
  publisher_name: string;
  account_label: string;
  account_handle: string;
  account_url: string;
  post_url: string;
  content: string;
  signal_tags: string[];
  matched_keywords?: string[];
  primary_keyword?: string | null;
  source_info: BackendSourceInfo;
  published_at: string;
  category?: string;
  severity?: string;
  region?: string;
  location?: { lat: number; lng: number };
  location_name?: string;
  risk_score?: number;
  keywords?: string[];
  is_safety_relevant?: boolean;
  ai_signals?: string[] | null;
  ai_scenario?: string | null;
  ai_severity?: string | null;
  ai_confidence?: number | null;
  ai_is_rumor?: boolean | null;
  ai_sentiment?: string | null;
  location_resolution_method?: string;
  ai_analysis_status?: string;
  ai_location_names?: string[];
};

type BackendOfficialFeedSource = {
  id: string;
  source_type: string;
  name: string;
  username: string;
  telegram_id: number | null;
  is_active: boolean;
  is_custom: boolean;
  created_at: string;
};

export type BackendDashboardSnapshot = {
  incidents: Incident[];
  alerts: Alert[];
  riskScores: RiskScore[];
  trendData: TrendDataPoint[];
  stats: DashboardStats;
};

const TOKEN_STORAGE_KEY = "crisisshield.backend.token";
const LIVE_FEED_WINDOW_MS = 48 * 60 * 60 * 1000;

let tokenCache: string | null = null;
let loginPromise: Promise<string> | null = null;

function parseTimestamp(value: string): number {
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : Number.NaN;
}

function isWithinLiveFeedWindow(value: string): boolean {
  const timestamp = parseTimestamp(value);
  if (!Number.isFinite(timestamp)) return false;
  return timestamp >= Date.now() - LIVE_FEED_WINDOW_MS;
}

function sortIncidentsNewestFirst(items: Incident[]): Incident[] {
  return [...items].sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime());
}

function sortOfficialPostsNewestFirst(items: OfficialFeedPost[]): OfficialFeedPost[] {
  return [...items].sort((left, right) => new Date(right.publishedAt).getTime() - new Date(left.publishedAt).getTime());
}

function getStoredToken(): string | null {
  if (tokenCache) return tokenCache;
  if (typeof window === "undefined") return null;
  const stored = window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
  tokenCache = stored;
  return stored;
}

function storeToken(token: string | null): void {
  tokenCache = token;
  if (typeof window === "undefined") return;
  if (token) {
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

function normalizeCredibility(value: string): CredibilityLevel {
  if (value === "verified" || value === "high" || value === "moderate" || value === "low" || value === "unverified") {
    return value;
  }
  return "moderate";
}

function normalizeSourceType(value: string): SourceInfo["type"] {
  if (
    value === "tv" ||
    value === "newspaper" ||
    value === "news_agency" ||
    value === "social_media" ||
    value === "government" ||
    value === "ngo" ||
    value === "sensor"
  ) {
    return value;
  }
  return "newspaper";
}

function normalizeIncidentCategory(value: string): Incident["category"] {
  if (
    value === "violence" ||
    value === "protest" ||
    value === "natural_disaster" ||
    value === "infrastructure" ||
    value === "health" ||
    value === "terrorism" ||
    value === "cyber" ||
    value === "other"
  ) {
    return value;
  }
  return "other";
}

function normalizeIncidentSeverity(value: string): Incident["severity"] {
  if (value === "low" || value === "medium" || value === "high" || value === "critical") {
    return value;
  }
  return "medium";
}

function normalizeIncidentStatus(value: string): Incident["status"] {
  if (
    value === "new" ||
    value === "processing" ||
    value === "analyzed" ||
    value === "escalated" ||
    value === "resolved" ||
    value === "false_alarm"
  ) {
    return value;
  }
  return "new";
}

function normalizeAlertSeverity(value: string): Alert["severity"] {
  if (value === "info" || value === "warning" || value === "critical" || value === "emergency") {
    return value;
  }
  return "info";
}

function mapSourceInfo(source: BackendSourceInfo): SourceInfo {
  return {
    name: source.name,
    type: normalizeSourceType(source.type),
    credibility: normalizeCredibility(source.credibility),
    credibilityScore: source.credibilityScore,
    logoInitials: source.logoInitials,
    url: source.url,
    verifiedBy: source.verifiedBy ?? [],
  };
}

function mapIncident(incident: BackendIncident): Incident {
  return {
    id: incident.id,
    source: incident.source,
    sourceInfo: mapSourceInfo(incident.source_info),
    sourceUrl: incident.source_url,
    title: incident.title,
    description: incident.description,
    category: normalizeIncidentCategory(incident.category),
    severity: normalizeIncidentSeverity(incident.severity),
    location: incident.location,
    locationName: incident.location_name,
    region: incident.region,
    sentimentScore: incident.sentiment_score,
    riskScore: incident.risk_score,
    entities: incident.entities,
    keywords: incident.keywords,
    status: normalizeIncidentStatus(incident.status),
    createdAt: incident.created_at,
  };
}

function mapRiskScore(score: BackendRiskScore): RiskScore {
  return {
    region: score.region,
    overallScore: score.overall_score,
    sentimentComponent: score.sentiment_component,
    volumeComponent: score.volume_component,
    keywordComponent: score.keyword_component,
    behaviorComponent: score.behavior_component,
    geospatialComponent: score.geospatial_component,
    confidence: score.confidence,
    calculatedAt: score.calculated_at,
  };
}

function mapAlert(alert: BackendAlert): Alert {
  return {
    id: alert.id,
    alertType: alert.alert_type,
    severity: normalizeAlertSeverity(alert.severity),
    title: alert.title,
    message: alert.message,
    recommendation: alert.recommendation,
    region: alert.region,
    isAcknowledged: alert.is_acknowledged,
    createdAt: alert.created_at,
    linkedIncidents: alert.linked_incidents,
  };
}

function mapOfficialFeedPost(post: BackendOfficialFeedPost): OfficialFeedPost {
  return {
    id: post.id,
    sourceId: post.source_id,
    isCustom: post.is_custom,
    platform: post.platform === "x" ? "x" : "telegram",
    publisherName: post.publisher_name,
    accountLabel: post.account_label,
    accountHandle: post.account_handle,
    accountUrl: post.account_url,
    postUrl: post.post_url,
    content: post.content,
    signalTags: post.signal_tags ?? [],
    matchedKeywords: post.matched_keywords ?? [],
    primaryKeyword: post.primary_keyword ?? null,
    sourceInfo: mapSourceInfo(post.source_info),
    publishedAt: post.published_at,
    category: post.category ?? "other",
    severity: (post.severity as OfficialFeedPost["severity"]) ?? "medium",
    region: post.region ?? "Beirut",
    location: post.location ?? { lat: 33.8938, lng: 35.5018 },
    locationName: post.location_name ?? "Lebanon",
    riskScore: post.risk_score ?? 0,
    keywords: post.keywords ?? [],
    isSafetyRelevant: post.is_safety_relevant ?? false,
    aiSignals: post.ai_signals ?? null,
    aiScenario: post.ai_scenario ?? null,
    aiSeverity: post.ai_severity ?? null,
    aiConfidence: post.ai_confidence ?? null,
    aiIsRumor: post.ai_is_rumor ?? null,
    aiSentiment: post.ai_sentiment ?? null,
    locationResolutionMethod: (post.location_resolution_method ?? 'none') as OfficialFeedPost['locationResolutionMethod'],
    aiAnalysisStatus: (post.ai_analysis_status ?? 'missing_key') as OfficialFeedPost['aiAnalysisStatus'],
    aiLocationNames: post.ai_location_names ?? [],
  };
}

function mapOfficialFeedSource(source: BackendOfficialFeedSource): OfficialFeedSource {
  return {
    id: source.id,
    sourceType: source.source_type === "rss" ? "rss" : "telegram",
    name: source.name,
    username: source.username,
    telegramId: source.telegram_id ?? null,
    isActive: source.is_active,
    isCustom: source.is_custom,
    createdAt: source.created_at,
  };
}

function severityRank(severity: Incident["severity"]): number {
  return severity === "critical" ? 4 : severity === "high" ? 3 : severity === "medium" ? 2 : 1;
}

function buildAlertsFromIncidents(incidents: Incident[]): Alert[] {
  return incidents
    .filter((incident) => incident.severity === "critical" || incident.severity === "high")
    .slice(0, 10)
    .map((incident) => ({
      id: `live-alert-${incident.id}`,
      alertType: incident.severity === "critical" ? "threshold_breach" : "escalation",
      severity: incident.severity === "critical" ? "emergency" : "warning",
      title: incident.title,
      message: incident.description,
      recommendation: `Verify via ${incident.sourceInfo.name}, monitor for escalation, and brief teams operating in ${incident.region}.`,
      region: incident.region,
      isAcknowledged: false,
      createdAt: incident.createdAt,
      linkedIncidents: [incident.id],
    }));
}

function buildRiskScoresFromIncidents(incidents: Incident[]): RiskScore[] {
  const byRegion = new Map<string, Incident[]>();
  for (const incident of incidents) {
    const current = byRegion.get(incident.region) ?? [];
    current.push(incident);
    byRegion.set(incident.region, current);
  }

  return Array.from(byRegion.entries())
    .map(([region, regionIncidents]) => {
      const avgRisk = regionIncidents.reduce((sum, incident) => sum + incident.riskScore, 0) / regionIncidents.length;
      const avgSentiment = regionIncidents.reduce((sum, incident) => sum + incident.sentimentScore, 0) / regionIncidents.length;
      const avgKeywords = regionIncidents.reduce((sum, incident) => sum + incident.keywords.length, 0) / regionIncidents.length;
      const criticalShare = regionIncidents.filter((incident) => incident.severity === "critical").length / regionIncidents.length;
      const highShare = regionIncidents.filter((incident) => incident.severity === "high").length / regionIncidents.length;

      return {
        region,
        overallScore: Number(avgRisk.toFixed(2)),
        sentimentComponent: Number(Math.max(0, Math.min(100, 50 + avgSentiment * 50)).toFixed(2)),
        volumeComponent: Number(Math.min(100, regionIncidents.length * 22).toFixed(2)),
        keywordComponent: Number(Math.min(100, avgKeywords * 16).toFixed(2)),
        behaviorComponent: Number(Math.min(100, 25 + highShare * 35 + criticalShare * 40).toFixed(2)),
        geospatialComponent: Number(Math.min(100, 30 + severityRank(regionIncidents[0].severity) * 12).toFixed(2)),
        confidence: 0.72,
        calculatedAt: new Date().toISOString(),
      } satisfies RiskScore;
    })
    .sort((left, right) => right.overallScore - left.overallScore);
}

function buildTrendDataFromIncidents(incidents: Incident[]): TrendDataPoint[] {
  const now = Date.now();
  const buckets = Array.from({ length: 24 }, (_, index) => {
    const bucketTime = new Date(now - (23 - index) * 60 * 60 * 1000);
    return {
      time: bucketTime.toISOString(),
      incidents: 0,
      riskSum: 0,
      sentimentSum: 0,
    };
  });

  for (const incident of incidents) {
    const createdAt = new Date(incident.createdAt).getTime();
    if (!Number.isFinite(createdAt)) continue;
    const hoursAgo = Math.floor((now - createdAt) / (60 * 60 * 1000));
    if (hoursAgo < 0 || hoursAgo > 23) continue;
    const bucketIndex = 23 - hoursAgo;
    const bucket = buckets[bucketIndex];
    bucket.incidents += 1;
    bucket.riskSum += incident.riskScore;
    bucket.sentimentSum += incident.sentimentScore;
  }

  return buckets.map((bucket) => ({
    time: bucket.time,
    incidents: bucket.incidents,
    riskScore: bucket.incidents ? Number((bucket.riskSum / bucket.incidents).toFixed(2)) : 0,
    sentiment: bucket.incidents ? Number((bucket.sentimentSum / bucket.incidents).toFixed(2)) : 0,
  }));
}

function buildStatsFromIncidents(incidents: Incident[], riskScores: RiskScore[], trendData: TrendDataPoint[]): DashboardStats {
  const cutoff24h = Date.now() - 24 * 60 * 60 * 1000;
  const recentIncidents = incidents.filter((incident) => {
    const createdAt = new Date(incident.createdAt).getTime();
    return Number.isFinite(createdAt) && createdAt >= cutoff24h;
  });
  const baseIncidents = recentIncidents.length > 0 ? recentIncidents : incidents;
  const avgRiskScore = baseIncidents.length
    ? Number((baseIncidents.reduce((sum, incident) => sum + incident.riskScore, 0) / baseIncidents.length).toFixed(2))
    : 0;
  const topRiskRegion = riskScores[0]?.region || "Unknown";
  const currentTrend = trendData.at(-1)?.riskScore ?? 0;
  const previousTrend = trendData.at(-2)?.riskScore ?? currentTrend;

  return {
    totalIncidents24h: baseIncidents.length,
    activeAlerts: baseIncidents.filter((incident) => incident.severity === "critical" || incident.severity === "high").length,
    avgRiskScore,
    riskTrend: Number((currentTrend - previousTrend).toFixed(1)),
    highestRiskRegion: topRiskRegion,
  };
}

function buildSnapshotFromLiveIncidents(liveIncidents: BackendIncident[]): BackendDashboardSnapshot {
  const incidents = sortIncidentsNewestFirst(
    liveIncidents
      .map(mapIncident)
      .filter((incident) => isWithinLiveFeedWindow(incident.createdAt)),
  );
  const riskScores = buildRiskScoresFromIncidents(incidents);
  const trendData = buildTrendDataFromIncidents(incidents);
  const alerts = buildAlertsFromIncidents(incidents);
  const stats = buildStatsFromIncidents(incidents, riskScores, trendData);

  return {
    incidents,
    alerts,
    riskScores,
    trendData,
    stats,
  };
}

async function loginToBackend(): Promise<string> {
  const cached = getStoredToken();
  if (cached) return cached;
  if (loginPromise) return loginPromise;

  loginPromise = (async () => {
    const response = await fetch(`${runtimeConfig.backendApiBaseUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: runtimeConfig.backendDevEmail,
        password: runtimeConfig.backendDevPassword,
      }),
    });

    const payload = (await response.json()) as ApiEnvelope<{ access_token: string }>;
    if (!response.ok || !payload.success || !payload.data?.access_token) {
      throw new Error(payload.error || "Backend login failed");
    }

    storeToken(payload.data.access_token);
    return payload.data.access_token;
  })();

  try {
    return await loginPromise;
  } finally {
    loginPromise = null;
  }
}

async function requestBackend<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  if (!runtimeConfig.hasBackendApi) {
    throw new Error("Backend API is not configured");
  }

  const requestUrl = `${runtimeConfig.backendApiBaseUrl}${path}`;
  const isLiveIncidentsRequest = path.startsWith("/api/v1/incidents/live");
  if (isLiveIncidentsRequest) {
    console.log("[backendApi] live incidents request URL:", requestUrl);
  }

  const token = await loginToBackend();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(requestUrl, {
    ...init,
    headers,
  });

  const rawBody = await response.text();
  let payload: ApiEnvelope<T> | Record<string, unknown> | null = null;
  try {
    payload = rawBody ? (JSON.parse(rawBody) as ApiEnvelope<T> | Record<string, unknown>) : null;
  } catch {
    payload = null;
  }

  if (isLiveIncidentsRequest) {
    console.log("[backendApi] live incidents response status:", response.status);
    console.log("[backendApi] live incidents response body:", payload ?? rawBody);
  }

  if (response.status === 401 && retry) {
    storeToken(null);
    return requestBackend<T>(path, init, false);
  }

  if (!payload) {
    if (!response.ok) {
      throw new Error(`Backend request failed (${response.status})`);
    }
    throw new Error(`Backend response was not valid JSON (${response.status})`);
  }

  const payloadRecord = payload as Record<string, unknown>;
  const errorMessage = extractBackendErrorMessage(payloadRecord, response.status);

  if (!response.ok) {
    throw new Error(errorMessage);
  }

  const isEnvelope = typeof payloadRecord.success === "boolean" && "data" in payloadRecord;
  if (!isEnvelope) {
    throw new Error(errorMessage);
  }

  if (!payloadRecord.success) {
    throw new Error(errorMessage);
  }

  return payloadRecord.data as T;
}

function extractBackendErrorMessage(payload: Record<string, unknown>, status: number): string {
  const error = payload.error;
  if (typeof error === "string" && error.trim()) {
    return error;
  }

  const detail = payload.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const firstDetail = detail[0];
    if (firstDetail && typeof firstDetail === "object" && "msg" in firstDetail) {
      const message = firstDetail.msg;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }
  }

  return `Backend request failed (${status})`;
}

export async function fetchBackendDashboardSnapshot(): Promise<BackendDashboardSnapshot> {
  const [liveIncidents, overview, incidentsPage, alerts, riskScores, trendData] = await Promise.all([
    requestBackend<BackendIncident[]>("/api/v1/incidents/live?limit=100").catch(() => []),
    requestBackend<BackendOverview>("/api/v1/dashboard/overview"),
    requestBackend<{ items: BackendIncident[]; page: number; per_page: number; total: number }>("/api/v1/incidents?page=1&per_page=100"),
    requestBackend<BackendAlert[]>("/api/v1/alerts"),
    requestBackend<BackendRiskScore[]>("/api/v1/risk/current"),
    requestBackend<BackendTrendPoint[]>("/api/v1/dashboard/trends"),
  ]);

  if (liveIncidents.length > 0) {
    return buildSnapshotFromLiveIncidents(liveIncidents);
  }

  const mappedTrendData = trendData.map((point) => ({
    time: point.time,
    incidents: point.incidents,
    riskScore: point.risk_score,
    sentiment: point.sentiment,
  }));

  const previousPoint = mappedTrendData.at(-2);
  const currentPoint = mappedTrendData.at(-1);
  const riskTrend = previousPoint && currentPoint ? Number((currentPoint.riskScore - previousPoint.riskScore).toFixed(1)) : 0;

  return {
    incidents: sortIncidentsNewestFirst(
      incidentsPage.items
        .map(mapIncident)
        .filter((incident) => isWithinLiveFeedWindow(incident.createdAt)),
    ),
    alerts: alerts.map(mapAlert),
    riskScores: riskScores.map(mapRiskScore),
    trendData: mappedTrendData,
    stats: {
      totalIncidents24h: overview.total_incidents_24h,
      activeAlerts: overview.active_alerts,
      avgRiskScore: overview.avg_risk_score,
      riskTrend,
      highestRiskRegion: overview.top_risk_region,
    },
  };
}

export async function acknowledgeBackendAlert(alertId: string): Promise<Alert> {
  const alert = await requestBackend<BackendAlert>(`/api/v1/alerts/${alertId}/acknowledge`, {
    method: "PATCH",
  });
  return mapAlert(alert);
}

export async function fetchBackendOfficialFeedPosts(limit = 50): Promise<OfficialFeedPost[]> {
  const posts = await requestBackend<BackendOfficialFeedPost[]>(`/api/v1/official-feeds?limit=${limit}`);
  return sortOfficialPostsNewestFirst(
    posts
      .map(mapOfficialFeedPost)
      .filter((post) => isWithinLiveFeedWindow(post.publishedAt)),
  );
}

export async function fetchBackendOfficialFeedSources(): Promise<OfficialFeedSource[]> {
  const sources = await requestBackend<BackendOfficialFeedSource[]>("/api/v1/official-feeds/sources");
  return sources.map(mapOfficialFeedSource);
}

export async function createBackendOfficialFeedSource(input: string): Promise<OfficialFeedSource> {
  const source = await requestBackend<BackendOfficialFeedSource>("/api/v1/official-feeds/sources", {
    method: "POST",
    body: JSON.stringify({
      source_type: "telegram",
      input,
    }),
  });
  return mapOfficialFeedSource(source);
}

export async function deleteBackendOfficialFeedSource(sourceId: string): Promise<OfficialFeedSource> {
  const source = await requestBackend<BackendOfficialFeedSource>(`/api/v1/official-feeds/sources/${sourceId}`, {
    method: "DELETE",
  });
  return mapOfficialFeedSource(source);
}

export async function fetchBackendLiveIncidents(limit = 100): Promise<Incident[]> {
  const numericLimit = Number.isFinite(limit) ? Math.trunc(limit) : 100;
  const safeLimit = Math.min(100, Math.max(1, numericLimit || 100));
  const incidents = await requestBackend<BackendIncident[]>(`/api/v1/incidents/live?limit=${safeLimit}`);
  return sortIncidentsNewestFirst(
    incidents
      .map(mapIncident)
      .filter((incident) => isWithinLiveFeedWindow(incident.createdAt)),
  );
}

// ── Hate Speech Monitor ───────────────────────────────────────────────────────

export type HateSpeechPost = {
  id: string;
  platform: string;
  authorHandle: string;
  authorAgeDays: number | null;
  content: string;
  language: string;
  hateScore: number;
  category: string;
  categoryLabel: string;
  isFlagged: boolean;
  keywordMatches: string[];
  modelConfidence: number;
  likeCount: number;
  retweetCount: number;
  replyCount: number;
  engagementTotal: number;
  postedAt: string;
  scrapedAt: string;
  sourceUrl: string;
  hashtags: string[];
  reviewed: boolean;
  reviewAction: string;
  // Trend-first fields
  matchedTrend: string;        // which Lebanon trend this tweet was found under
  engagementVelocity: number;  // engagement per hour (virality signal, 0–100)
  priorityScore: number;       // combined risk + velocity + trend rank (0–100)
};

export type HateSpeechTrendCluster = {
  trend: string;
  displayName: string;
  tweetVolume: number | null;
  trendRank: number;
  postCount: number;
  flaggedCount: number;
  avgRiskScore: number;
  maxRiskScore: number;
  totalEngagement: number;
  topPostIds: string[];
  source: string;
  flagRate: number;
  riskLevel: 'critical' | 'high' | 'medium' | 'low';
};

export type HateSpeechSortOption = 'priority' | 'score' | 'engagement' | 'velocity' | 'recent';

export type HateSpeechStats = {
  totalScraped: number;
  totalFlagged: number;
  flaggedLast24h: number;
  flaggedLast1h: number;
  byCategory: Record<string, number>;
  byCategoryLabels: Record<string, string>;
  byLanguage: Record<string, number>;
  topKeywords: [string, number][];
  lastScanAt: string | null;
  accountsFlagged: string[];
  trendingHashtags: string[];
  topPostsByEngagement: string[];
  hashtagTopPosts: Record<string, string[]>;
  activeTrends: HateSpeechTrendCluster[];
};

export type HateSpeechReply = {
  id: string;
  authorHandle: string;
  content: string;
  language: string;
  likeCount: number;
  retweetCount: number;
  replyCount: number;
  engagementTotal: number;
  postedAt: string;
  sourceUrl: string;
};

type BackendHateSpeechPost = {
  id: string;
  platform: string;
  author_handle: string;
  author_age_days: number | null;
  content: string;
  language: string;
  hate_score: number;
  category: string;
  category_label: string;
  is_flagged: boolean;
  keyword_matches: string[];
  model_confidence: number;
  like_count: number;
  retweet_count: number;
  reply_count: number;
  engagement_total: number;
  posted_at: string;
  scraped_at: string;
  source_url: string;
  hashtags: string[];
  reviewed: boolean;
  review_action: string;
  matched_trend: string;
  engagement_velocity: number;
  priority_score: number;
};

type BackendTrendCluster = {
  trend: string;
  display_name: string;
  tweet_volume: number | null;
  trend_rank: number;
  post_count: number;
  flagged_count: number;
  avg_risk_score: number;
  max_risk_score: number;
  total_engagement: number;
  top_post_ids: string[];
  source: string;
  flag_rate: number;
  risk_level: string;
};

type BackendHateSpeechStats = {
  total_scraped: number;
  total_flagged: number;
  flagged_last_24h: number;
  flagged_last_1h: number;
  by_category: Record<string, number>;
  by_category_labels: Record<string, string>;
  by_language: Record<string, number>;
  top_keywords: [string, number][];
  last_scan_at: string | null;
  accounts_flagged: string[];
  trending_hashtags?: string[];
  top_posts_by_engagement?: string[];
  hashtag_top_posts?: Record<string, string[]>;
  active_trends?: BackendTrendCluster[];
};

function mapTrendCluster(c: BackendTrendCluster): HateSpeechTrendCluster {
  return {
    trend: c.trend,
    displayName: c.display_name,
    tweetVolume: c.tweet_volume,
    trendRank: c.trend_rank,
    postCount: c.post_count,
    flaggedCount: c.flagged_count,
    avgRiskScore: c.avg_risk_score,
    maxRiskScore: c.max_risk_score,
    totalEngagement: c.total_engagement,
    topPostIds: c.top_post_ids,
    source: c.source,
    flagRate: c.flag_rate,
    riskLevel: (c.risk_level as HateSpeechTrendCluster['riskLevel']) ?? 'low',
  };
}

function mapHateSpeechPost(post: BackendHateSpeechPost): HateSpeechPost {
  return {
    id: post.id,
    platform: post.platform,
    authorHandle: post.author_handle,
    authorAgeDays: post.author_age_days,
    content: post.content,
    language: post.language,
    hateScore: post.hate_score,
    category: post.category,
    categoryLabel: post.category_label,
    isFlagged: post.is_flagged,
    keywordMatches: post.keyword_matches,
    modelConfidence: post.model_confidence,
    likeCount: post.like_count,
    retweetCount: post.retweet_count,
    replyCount: post.reply_count,
    engagementTotal: post.engagement_total,
    postedAt: post.posted_at,
    scrapedAt: post.scraped_at,
    sourceUrl: post.source_url,
    hashtags: post.hashtags,
    reviewed: post.reviewed,
    reviewAction: post.review_action,
    matchedTrend: post.matched_trend ?? '',
    engagementVelocity: post.engagement_velocity ?? 0,
    priorityScore: post.priority_score ?? 0,
  };
}

export async function fetchHateSpeechStats(): Promise<HateSpeechStats> {
  const data = await requestBackend<BackendHateSpeechStats>("/api/v1/hate-speech/stats");
  return {
    totalScraped: data.total_scraped,
    totalFlagged: data.total_flagged,
    flaggedLast24h: data.flagged_last_24h,
    flaggedLast1h: data.flagged_last_1h,
    byCategory: data.by_category,
    byCategoryLabels: data.by_category_labels,
    byLanguage: data.by_language,
    topKeywords: data.top_keywords,
    lastScanAt: data.last_scan_at,
    accountsFlagged: data.accounts_flagged,
    trendingHashtags: data.trending_hashtags ?? [],
    topPostsByEngagement: data.top_posts_by_engagement ?? [],
    hashtagTopPosts: data.hashtag_top_posts ?? {},
    activeTrends: (data.active_trends ?? []).map(mapTrendCluster),
  };
}

export async function fetchHateSpeechTrends(): Promise<HateSpeechTrendCluster[]> {
  const clusters = await requestBackend<BackendTrendCluster[]>("/api/v1/hate-speech/trends");
  return clusters.map(mapTrendCluster);
}

export async function fetchHateSpeechPosts(params: {
  category?: string;
  minScore?: number;
  reviewed?: boolean;
  limit?: number;
  sort?: HateSpeechSortOption;
}): Promise<HateSpeechPost[]> {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  if (params.minScore !== undefined) query.set("min_score", String(params.minScore));
  if (params.reviewed !== undefined) query.set("reviewed", String(params.reviewed));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.sort) query.set("sort", params.sort);
  const qs = query.toString();
  const posts = await requestBackend<BackendHateSpeechPost[]>(`/api/v1/hate-speech/posts${qs ? "?" + qs : ""}`);
  return posts.map(mapHateSpeechPost);
}

export async function fetchHateSpeechAllPosts(params: {
  hours?: number;
  limit?: number;
  sort?: HateSpeechSortOption;
}): Promise<HateSpeechPost[]> {
  const query = new URLSearchParams();
  if (params.hours !== undefined) query.set("hours", String(params.hours));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.sort) query.set("sort", params.sort);
  const qs = query.toString();
  const posts = await requestBackend<BackendHateSpeechPost[]>(`/api/v1/hate-speech/all${qs ? "?" + qs : ""}`);
  return posts.map(mapHateSpeechPost);
}

export async function fetchHateSpeechPostsByTrend(
  trendName: string,
  limit = 20,
): Promise<HateSpeechPost[]> {
  const posts = await requestBackend<BackendHateSpeechPost[]>(
    `/api/v1/hate-speech/trend/${encodeURIComponent(trendName)}?limit=${limit}`,
  );
  return posts.map(mapHateSpeechPost);
}

export async function triggerHateSpeechScan(): Promise<Record<string, unknown>> {
  return requestBackend<Record<string, unknown>>("/api/v1/hate-speech/scan", { method: "POST" });
}

export async function reviewHateSpeechPost(
  postId: string,
  action: "confirmed" | "dismissed",
): Promise<{ postId: string; action: string }> {
  const result = await requestBackend<{ post_id: string; action: string }>(
    `/api/v1/hate-speech/posts/${postId}/review`,
    { method: "POST", body: JSON.stringify({ action }) },
  );
  return { postId: result.post_id, action: result.action };
}

type BackendReply = {
  id: string;
  author_handle: string;
  content: string;
  language: string;
  like_count: number;
  retweet_count: number;
  reply_count: number;
  engagement_total: number;
  posted_at: string;
  source_url: string;
};

export async function fetchHateSpeechReplies(postId: string, limit = 10): Promise<HateSpeechReply[]> {
  const replies = await requestBackend<BackendReply[]>(
    `/api/v1/hate-speech/posts/${encodeURIComponent(postId)}/replies?limit=${limit}`,
  );
  return replies.map((r) => ({
    id: r.id,
    authorHandle: r.author_handle,
    content: r.content,
    language: r.language,
    likeCount: r.like_count,
    retweetCount: r.retweet_count,
    replyCount: r.reply_count,
    engagementTotal: r.engagement_total,
    postedAt: r.posted_at,
    sourceUrl: r.source_url,
  }));
}

export async function fetchHateSpeechSearch(query: string, limit = 10): Promise<HateSpeechPost[]> {
  const q = query.startsWith('#') ? query.slice(1) : query;
  const posts = await requestBackend<BackendHateSpeechPost[]>(
    `/api/v1/hate-speech/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
  return posts.map(mapHateSpeechPost);
}

export type HateSpeechAgentStatus = {
  mode: string;
  isRunning: boolean;
  scanCount: number;
  totalPostsDiscovered: number;
  lastScanAt: string | null;
  lastScanDurationSeconds: number;
  lastScanPostsFound: number;
  nextScanAt: string | null;
  sourcesLastScan: string[];
  queriesUsed: number;
  discoveryStrategies: string[];
  scanIntervalSeconds: number;
  currentPostsInStore: number;
  description: string;
};

export async function fetchHateSpeechAgentStatus(): Promise<HateSpeechAgentStatus> {
  const data = await requestBackend<{
    mode: string;
    is_running: boolean;
    scan_count: number;
    total_posts_discovered: number;
    last_scan_at: string | null;
    last_scan_duration_seconds: number;
    last_scan_posts_found: number;
    next_scan_at: string | null;
    sources_last_scan: string[];
    queries_used: number;
    discovery_strategies: string[];
    scan_interval_seconds: number;
    current_posts_in_store: number;
    description: string;
  }>("/api/v1/hate-speech/agent-status");
  return {
    mode: data.mode,
    isRunning: data.is_running,
    scanCount: data.scan_count,
    totalPostsDiscovered: data.total_posts_discovered,
    lastScanAt: data.last_scan_at,
    lastScanDurationSeconds: data.last_scan_duration_seconds,
    lastScanPostsFound: data.last_scan_posts_found,
    nextScanAt: data.next_scan_at,
    sourcesLastScan: data.sources_last_scan,
    queriesUsed: data.queries_used,
    discoveryStrategies: data.discovery_strategies,
    scanIntervalSeconds: data.scan_interval_seconds,
    currentPostsInStore: data.current_posts_in_store,
    description: data.description,
  };
}
