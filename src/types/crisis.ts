export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type AlertSeverity = 'info' | 'warning' | 'critical' | 'emergency';
// armed_conflict added per blueprint Section 0.4.2
export type IncidentCategory =
  | 'violence'
  | 'protest'
  | 'natural_disaster'
  | 'infrastructure'
  | 'health'
  | 'terrorism'
  | 'cyber'
  | 'armed_conflict'
  | 'other';
export type IncidentStatus = 'new' | 'processing' | 'analyzed' | 'escalated' | 'resolved' | 'false_alarm';
// Section 0.4.3 verification states
export type VerificationStatus = 'unverified' | 'reviewed' | 'confirmed' | 'rejected';
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

  // Section 0.4.3 — Data integrity fields
  verificationStatus?: VerificationStatus;
  confidenceScore?: number;
  processedText?: string;

  // Section 0.4.4 — Analyst workflow fields
  reviewedBy?: string;
  reviewedAt?: string;
  analystNotes?: string;
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
  // Prediction / anomaly fields
  isAnomalous?: boolean;
  anomalyScore?: number;
  escalationProbability?: number;
  incidentCount24h?: number;
}

export interface RiskPrediction {
  region: string;
  horizon: '24h' | '48h' | '7d';
  predictedScore: number;
  lowerBound: number;
  upperBound: number;
  confidence: number;
  escalationProbability: number;
  predictedFor: string;
  modelVersion: string;
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
  acknowledgedBy?: string;
  acknowledgedAt?: string;
  createdAt: string;
  linkedIncidents: string[];
  notificationChannels?: string[];
}

export interface AlertStats {
  total: number;
  acknowledged: number;
  bySeverity: Record<string, number>;
  averageResponseMinutes: number;
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
  isSafetyRelevant: boolean;
  category: IncidentCategory;
  severity: Severity;
  region: string;
  locationName: string;
  location: { lat: number; lng: number };
  riskScore: number;
  keywords: string[];
}

// Region detail with full breakdown (from /risk/region/{region})
export interface RegionRiskDetail extends RiskScore {
  isAnomalous: boolean;
  anomalyScore: number | null;
  escalationProbability: number | null;
  incidentCount24h: number;
}
