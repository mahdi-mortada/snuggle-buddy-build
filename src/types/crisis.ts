export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type AlertSeverity = 'info' | 'warning' | 'critical' | 'emergency';
export type IncidentCategory = 'violence' | 'protest' | 'natural_disaster' | 'infrastructure' | 'health' | 'terrorism' | 'cyber' | 'other';
export type IncidentStatus = 'new' | 'processing' | 'analyzed' | 'escalated' | 'resolved' | 'false_alarm';
export type CredibilityLevel = 'verified' | 'high' | 'moderate' | 'low' | 'unverified';

export interface SourceInfo {
  name: string;
  type: 'tv' | 'newspaper' | 'news_agency' | 'social_media' | 'government' | 'ngo' | 'sensor';
  credibility: CredibilityLevel;
  credibilityScore: number; // 0-100
  logoInitials: string;
  url?: string;
  verifiedBy?: string[];
}

export interface Incident {
  id: string;
  source: string;
  sourceInfo: SourceInfo;
  sourceUrl?: string;
  title: string;
  description: string;
  category: IncidentCategory;
  severity: Severity;
  location: { lat: number; lng: number };
  locationName: string;
  region: string;
  sentimentScore: number;
  riskScore: number;
  entities: string[];
  keywords: string[];
  status: IncidentStatus;
  createdAt: string;
  corroboratedBy?: SourceInfo[];
}

export interface RiskScore {
  region: string;
  overallScore: number;
  sentimentComponent: number;
  volumeComponent: number;
  keywordComponent: number;
  behaviorComponent: number;
  geospatialComponent: number;
  confidence: number;
  calculatedAt: string;
}

export interface Alert {
  id: string;
  alertType: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  recommendation: string;
  region: string;
  isAcknowledged: boolean;
  createdAt: string;
  linkedIncidents: string[];
}

export interface DashboardStats {
  totalIncidents24h: number;
  activeAlerts: number;
  avgRiskScore: number;
  riskTrend: number;
  highestRiskRegion: string;
}

export interface TrendDataPoint {
  time: string;
  incidents: number;
  riskScore: number;
  sentiment: number;
}

export interface OfficialFeedPost {
  id: string;
  platform: 'telegram' | 'x';
  publisherName: string;
  accountLabel: string;
  accountHandle: string;
  accountUrl: string;
  postUrl: string;
  content: string;
  signalTags: string[];
  sourceInfo: SourceInfo;
  publishedAt: string;
}
