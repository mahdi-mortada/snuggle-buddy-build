import { runtimeConfig } from "@/lib/runtimeConfig";
import type { Alert, CredibilityLevel, DashboardStats, Incident, OfficialFeedPost, RiskScore, SourceInfo, TrendDataPoint } from "@/types/crisis";

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
  platform: string;
  publisher_name: string;
  account_label: string;
  account_handle: string;
  account_url: string;
  post_url: string;
  content: string;
  signal_tags: string[];
  source_info: BackendSourceInfo;
  published_at: string;
};

export type BackendDashboardSnapshot = {
  incidents: Incident[];
  alerts: Alert[];
  riskScores: RiskScore[];
  trendData: TrendDataPoint[];
  stats: DashboardStats;
};

const TOKEN_STORAGE_KEY = "crisisshield.backend.token";

let tokenCache: string | null = null;
let loginPromise: Promise<string> | null = null;

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
    platform: post.platform === "x" ? "x" : "telegram",
    publisherName: post.publisher_name,
    accountLabel: post.account_label,
    accountHandle: post.account_handle,
    accountUrl: post.account_url,
    postUrl: post.post_url,
    content: post.content,
    signalTags: post.signal_tags ?? [],
    sourceInfo: mapSourceInfo(post.source_info),
    publishedAt: post.published_at,
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
  const incidents = liveIncidents.map(mapIncident).sort(
    (left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
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

  const token = await loginToBackend();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${runtimeConfig.backendApiBaseUrl}${path}`, {
    ...init,
    headers,
  });

  if (response.status === 401 && retry) {
    storeToken(null);
    return requestBackend<T>(path, init, false);
  }

  const payload = (await response.json()) as ApiEnvelope<T>;
  if (!response.ok || !payload.success) {
    throw new Error(payload.error || `Backend request failed (${response.status})`);
  }

  return payload.data;
}

export async function fetchBackendDashboardSnapshot(): Promise<BackendDashboardSnapshot> {
  const [liveIncidents, overview, incidentsPage, alerts, riskScores, trendData] = await Promise.all([
    requestBackend<BackendIncident[]>("/api/v1/incidents/live?limit=30").catch(() => []),
    requestBackend<BackendOverview>("/api/v1/dashboard/overview"),
    requestBackend<{ items: BackendIncident[]; page: number; per_page: number; total: number }>("/api/v1/incidents?page=1&per_page=50"),
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
    incidents: incidentsPage.items.map(mapIncident),
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

export async function fetchBackendOfficialFeedPosts(limit = 24): Promise<OfficialFeedPost[]> {
  const posts = await requestBackend<BackendOfficialFeedPost[]>(`/api/v1/official-feeds?limit=${limit}`);
  return posts.map(mapOfficialFeedPost);
}
