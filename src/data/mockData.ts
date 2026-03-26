import type { Incident, RiskScore, Alert, DashboardStats, TrendDataPoint } from '@/types/crisis';

export const mockStats: DashboardStats = {
  totalIncidents24h: 247,
  activeAlerts: 12,
  avgRiskScore: 67.3,
  riskTrend: 4.2,
  highestRiskRegion: 'Beirut',
};

export const mockIncidents: Incident[] = [
  { id: '1', source: 'social_media', title: 'Large gathering reported near Martyrs Square', description: 'Multiple social media posts indicating a growing crowd near downtown Beirut.', category: 'protest', severity: 'high', location: { lat: 33.8938, lng: 35.5018 }, locationName: "Martyrs' Square", region: 'Beirut', sentimentScore: -0.72, riskScore: 78, entities: ['Beirut', 'Martyrs Square'], keywords: ['protest', 'gathering', 'crowd'], status: 'escalated', createdAt: new Date(Date.now() - 300000).toISOString() },
  { id: '2', source: 'news', title: 'Power grid failure in Tripoli industrial zone', description: 'Major power outage affecting northern industrial facilities.', category: 'infrastructure', severity: 'critical', location: { lat: 34.4367, lng: 35.8497 }, locationName: 'Tripoli Industrial Zone', region: 'North Lebanon', sentimentScore: -0.85, riskScore: 89, entities: ['Tripoli', 'EDL'], keywords: ['power outage', 'infrastructure', 'emergency'], status: 'new', createdAt: new Date(Date.now() - 120000).toISOString() },
  { id: '3', source: 'web_scraping', title: 'Flooding alerts in Bekaa Valley', description: 'Heavy rainfall causing flash flooding in agricultural areas.', category: 'natural_disaster', severity: 'high', location: { lat: 33.8463, lng: 35.9019 }, locationName: 'Bekaa Valley', region: 'Bekaa', sentimentScore: -0.65, riskScore: 72, entities: ['Bekaa Valley'], keywords: ['flood', 'rain', 'disaster'], status: 'analyzed', createdAt: new Date(Date.now() - 600000).toISOString() },
  { id: '4', source: 'social_media', title: 'Cyber attack targeting banking sector', description: 'Reports of coordinated phishing campaigns against Lebanese banks.', category: 'cyber', severity: 'critical', location: { lat: 33.8886, lng: 35.4955 }, locationName: 'Hamra District', region: 'Beirut', sentimentScore: -0.91, riskScore: 92, entities: ['Bank of Lebanon', 'Hamra'], keywords: ['cyber', 'attack', 'phishing', 'banking'], status: 'escalated', createdAt: new Date(Date.now() - 60000).toISOString() },
  { id: '5', source: 'manual', title: 'Health clinic overwhelmed in Sidon', description: 'Local clinic reports surge in respiratory illness cases.', category: 'health', severity: 'medium', location: { lat: 33.5633, lng: 35.3697 }, locationName: 'Sidon', region: 'South Lebanon', sentimentScore: -0.45, riskScore: 55, entities: ['Sidon', 'Ministry of Health'], keywords: ['health', 'clinic', 'respiratory'], status: 'processing', createdAt: new Date(Date.now() - 900000).toISOString() },
  { id: '6', source: 'news', title: 'Roadblock on Beirut-Damascus highway', description: 'Unidentified groups have set up roadblocks along the main highway.', category: 'violence', severity: 'high', location: { lat: 33.8700, lng: 35.7500 }, locationName: 'Dahr el Baydar', region: 'Mount Lebanon', sentimentScore: -0.78, riskScore: 81, entities: ['Beirut-Damascus Highway'], keywords: ['roadblock', 'highway', 'security'], status: 'new', createdAt: new Date(Date.now() - 180000).toISOString() },
  { id: '7', source: 'social_media', title: 'Suspicious package found near Jounieh port', description: 'Authorities investigating reports of unattended package.', category: 'terrorism', severity: 'critical', location: { lat: 33.9808, lng: 35.6178 }, locationName: 'Jounieh Port', region: 'Mount Lebanon', sentimentScore: -0.88, riskScore: 85, entities: ['Jounieh', 'LAF'], keywords: ['suspicious', 'package', 'port', 'investigation'], status: 'escalated', createdAt: new Date(Date.now() - 30000).toISOString() },
  { id: '8', source: 'sensor', title: 'Air quality deterioration in Baalbek', description: 'Sensor readings show PM2.5 levels exceeding safe thresholds.', category: 'health', severity: 'low', location: { lat: 34.0047, lng: 36.2110 }, locationName: 'Baalbek', region: 'Bekaa', sentimentScore: -0.20, riskScore: 35, entities: ['Baalbek', 'EPA'], keywords: ['air quality', 'pollution', 'PM2.5'], status: 'analyzed', createdAt: new Date(Date.now() - 1800000).toISOString() },
];

export const mockRiskScores: RiskScore[] = [
  { region: 'Beirut', overallScore: 78, sentimentComponent: 82, volumeComponent: 75, keywordComponent: 80, behaviorComponent: 68, geospatialComponent: 72, confidence: 0.89, calculatedAt: new Date().toISOString() },
  { region: 'North Lebanon', overallScore: 71, sentimentComponent: 76, volumeComponent: 68, keywordComponent: 74, behaviorComponent: 60, geospatialComponent: 65, confidence: 0.82, calculatedAt: new Date().toISOString() },
  { region: 'South Lebanon', overallScore: 55, sentimentComponent: 58, volumeComponent: 50, keywordComponent: 62, behaviorComponent: 45, geospatialComponent: 52, confidence: 0.78, calculatedAt: new Date().toISOString() },
  { region: 'Mount Lebanon', overallScore: 65, sentimentComponent: 70, volumeComponent: 60, keywordComponent: 68, behaviorComponent: 55, geospatialComponent: 62, confidence: 0.85, calculatedAt: new Date().toISOString() },
  { region: 'Bekaa', overallScore: 59, sentimentComponent: 55, volumeComponent: 65, keywordComponent: 58, behaviorComponent: 52, geospatialComponent: 48, confidence: 0.80, calculatedAt: new Date().toISOString() },
  { region: 'Nabatieh', overallScore: 42, sentimentComponent: 40, volumeComponent: 38, keywordComponent: 48, behaviorComponent: 35, geospatialComponent: 44, confidence: 0.75, calculatedAt: new Date().toISOString() },
  { region: 'Akkar', overallScore: 38, sentimentComponent: 35, volumeComponent: 42, keywordComponent: 40, behaviorComponent: 30, geospatialComponent: 36, confidence: 0.72, calculatedAt: new Date().toISOString() },
  { region: 'Baalbek-Hermel', overallScore: 48, sentimentComponent: 50, volumeComponent: 45, keywordComponent: 52, behaviorComponent: 42, geospatialComponent: 40, confidence: 0.77, calculatedAt: new Date().toISOString() },
];

export const mockAlerts: Alert[] = [
  { id: 'a1', alertType: 'threshold_breach', severity: 'emergency', title: 'Cyber Attack — Critical Infrastructure at Risk', message: 'Risk score for Beirut banking sector has exceeded emergency threshold (92/100). Coordinated phishing campaign detected targeting major financial institutions.', recommendation: 'Immediate Actions:\n1. Alert CERT Lebanon and financial sector security teams\n2. Issue public advisory about phishing attempts\n3. Activate emergency cyber response protocol\n4. Coordinate with ISPs to block identified malicious domains\n5. Deploy additional monitoring on financial network traffic', region: 'Beirut', isAcknowledged: false, createdAt: new Date(Date.now() - 60000).toISOString(), linkedIncidents: ['4'] },
  { id: 'a2', alertType: 'escalation', severity: 'critical', title: 'Infrastructure Failure — Power Grid Collapse', message: 'Power grid failure in Tripoli industrial zone. Risk score 89/100 with rapid escalation trajectory.', recommendation: 'Immediate Actions:\n1. Dispatch emergency repair crews to Tripoli\n2. Activate backup generators for critical facilities\n3. Coordinate with hospitals for power continuity\n4. Issue public communication about estimated restoration', region: 'North Lebanon', isAcknowledged: false, createdAt: new Date(Date.now() - 120000).toISOString(), linkedIncidents: ['2'] },
  { id: 'a3', alertType: 'prediction', severity: 'critical', title: 'Protest Escalation Predicted — Beirut Downtown', message: 'ML model predicts 87% probability of protest escalation within 24 hours based on social media sentiment and historical patterns.', recommendation: 'Preventive Actions:\n1. Increase security presence near Martyrs Square\n2. Establish communication channels with protest organizers\n3. Prepare crowd management resources\n4. Monitor social media for coordination signals', region: 'Beirut', isAcknowledged: true, createdAt: new Date(Date.now() - 300000).toISOString(), linkedIncidents: ['1'] },
  { id: 'a4', alertType: 'threshold_breach', severity: 'warning', title: 'Flooding Risk — Bekaa Valley Agricultural Zone', message: 'Sustained rainfall increasing flood risk. Current risk score 72/100 with upward trend.', recommendation: 'Preparatory Actions:\n1. Issue flood warnings to agricultural communities\n2. Prepare evacuation routes for low-lying areas\n3. Pre-position emergency supplies\n4. Monitor river levels and dam capacity', region: 'Bekaa', isAcknowledged: false, createdAt: new Date(Date.now() - 600000).toISOString(), linkedIncidents: ['3'] },
  { id: 'a5', alertType: 'anomaly', severity: 'critical', title: 'Suspicious Activity — Jounieh Port', message: 'Security alert triggered by suspicious package report. Enhanced monitoring engaged.', recommendation: 'Response Protocol:\n1. Establish security perimeter\n2. Deploy EOD team for assessment\n3. Evacuate nearby civilians\n4. Coordinate with port authority', region: 'Mount Lebanon', isAcknowledged: false, createdAt: new Date(Date.now() - 30000).toISOString(), linkedIncidents: ['7'] },
  { id: 'a6', alertType: 'trend', severity: 'warning', title: 'Rising Tension — Mount Lebanon Highway', message: 'Roadblock activity indicates potential escalation in Mount Lebanon region.', recommendation: 'Monitor and prepare alternative traffic routes. Coordinate with local authorities.', region: 'Mount Lebanon', isAcknowledged: true, createdAt: new Date(Date.now() - 180000).toISOString(), linkedIncidents: ['6'] },
  { id: 'a7', alertType: 'threshold_breach', severity: 'info', title: 'Air Quality Advisory — Baalbek', message: 'PM2.5 levels slightly elevated. Monitoring continues.', recommendation: 'Issue advisory for sensitive populations. Continue monitoring sensor data.', region: 'Bekaa', isAcknowledged: true, createdAt: new Date(Date.now() - 1800000).toISOString(), linkedIncidents: ['8'] },
];

export const mockTrendData: TrendDataPoint[] = Array.from({ length: 168 }, (_, i) => {
  const time = new Date(Date.now() - (167 - i) * 3600000);
  const base = 40 + Math.sin(i / 24 * Math.PI * 2) * 15;
  return {
    time: time.toISOString(),
    incidents: Math.floor(8 + Math.random() * 12 + (Math.sin(i / 12) * 5)),
    riskScore: Math.round((base + Math.random() * 20) * 10) / 10,
    sentiment: Math.round((-0.3 + Math.sin(i / 36) * 0.4 + Math.random() * 0.2) * 100) / 100,
  };
});

export const regionCoordinates: Record<string, { lat: number; lng: number }> = {
  'Beirut': { lat: 33.8938, lng: 35.5018 },
  'North Lebanon': { lat: 34.4367, lng: 35.8497 },
  'South Lebanon': { lat: 33.2721, lng: 35.2033 },
  'Mount Lebanon': { lat: 33.8100, lng: 35.5900 },
  'Bekaa': { lat: 33.8463, lng: 35.9019 },
  'Nabatieh': { lat: 33.3772, lng: 35.4836 },
  'Akkar': { lat: 34.5331, lng: 36.0781 },
  'Baalbek-Hermel': { lat: 34.0047, lng: 36.2110 },
};
