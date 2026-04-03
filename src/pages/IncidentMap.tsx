import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useLiveData } from '@/hooks/useLiveData';
import type { AlertSeverity, Incident, IncidentCategory, Severity } from '@/types/crisis';
import { GOVERNORATE_FEATURES, LEBANON_GEOJSON, type LebanonFeature } from '@/data/lebanon_geojson';

const severityRadius: Record<Severity, number> = {
  low: 6,
  medium: 8,
  high: 10,
  critical: 14,
};

const severityColor: Record<Severity, string> = {
  low: '#22C55E',
  medium: '#F59E0B',
  high: '#EF4444',
  critical: '#DC2626',
};

const alertSeverityRadius: Record<AlertSeverity, number> = {
  info: 6,
  warning: 9,
  critical: 12,
  emergency: 14,
};

const alertSeverityColor: Record<AlertSeverity, string> = {
  info: '#22C55E',
  warning: '#F59E0B',
  critical: '#EF4444',
  emergency: '#DC2626',
};

const categories: IncidentCategory[] = [
  'violence', 'protest', 'natural_disaster', 'infrastructure',
  'health', 'terrorism', 'cyber', 'armed_conflict', 'other',
];

const DISTRICT_FEATURES = LEBANON_GEOJSON.features.filter((feature) => feature.properties.type === 'district');
const GOVERNORATE_BY_ID = new Map(GOVERNORATE_FEATURES.map((feature) => [feature.properties.id, feature.properties.name]));
const LOCAL_INFLUENCE_RADIUS_DEGREES = 0.12;

function riskToColor(score: number): string {
  if (score >= 85) return '#dc2626';
  if (score >= 70) return '#ef4444';
  if (score >= 55) return '#f97316';
  if (score >= 40) return '#f59e0b';
  if (score >= 20) return '#eab308';
  return '#22c55e';
}

function riskStrokeColor(score: number): string {
  if (score >= 70) return 'rgba(254, 202, 202, 0.42)';
  if (score >= 40) return 'rgba(253, 224, 71, 0.28)';
  return 'rgba(148, 163, 184, 0.18)';
}

function riskFillOpacity(score: number): number {
  if (score >= 85) return 0.2;
  if (score >= 70) return 0.17;
  if (score >= 55) return 0.14;
  if (score >= 40) return 0.11;
  if (score >= 20) return 0.08;
  return 0.05;
}

function pointInPolygon(lat: number, lng: number, feature: LebanonFeature): boolean {
  const ring = feature.geometry.coordinates[0];
  let inside = false;

  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersects = ((yi > lat) !== (yj > lat))
      && (lng < ((xj - xi) * (lat - yi)) / ((yj - yi) || Number.EPSILON) + xi);
    if (intersects) inside = !inside;
  }

  return inside;
}

function distanceDegrees(latA: number, lngA: number, latB: number, lngB: number): number {
  const dLat = latA - latB;
  const dLng = lngA - lngB;
  return Math.sqrt(dLat * dLat + dLng * dLng);
}

function timeRangeToMs(timeRange: string): number {
  if (timeRange === '1h') return 1 * 3600 * 1000;
  if (timeRange === '6h') return 6 * 3600 * 1000;
  if (timeRange === '7d') return 7 * 24 * 3600 * 1000;
  return 24 * 3600 * 1000;
}

function filterIncidents(
  incidents: Incident[],
  alerts: { linkedIncidents: string[] }[],
  selectedCategories: Set<IncidentCategory>,
  timeRange: string,
): Incident[] {
  const cutoff = Date.now() - timeRangeToMs(timeRange);
  const alertIncidentIds = new Set(alerts.flatMap((alert) => alert.linkedIncidents));
  const hasAlertLinks = alertIncidentIds.size > 0;

  return incidents.filter((incident) => {
    const createdAt = new Date(incident.createdAt).getTime();
    const withinTime = Number.isFinite(createdAt) ? createdAt >= cutoff : true;
    const categoryOk = selectedCategories.has(incident.category);
    const alertOk = !hasAlertLinks || alertIncidentIds.has(incident.id);
    return withinTime && categoryOk && alertOk;
  });
}

function buildDistrictScore(
  feature: LebanonFeature,
  incidents: Incident[],
  regionRisk: number,
): number {
  const { centroid_lat: centroidLat, centroid_lng: centroidLng } = feature.properties;
  let weightedRisk = 0;
  let totalWeight = 0;
  let maxRisk = 0;

  for (const incident of incidents) {
    const incidentLat = incident.location.lat;
    const incidentLng = incident.location.lng;
    const inside = pointInPolygon(incidentLat, incidentLng, feature);
    const distance = inside ? 0 : distanceDegrees(incidentLat, incidentLng, centroidLat, centroidLng);
    const influence = inside
      ? 1
      : Math.max(0, 1 - distance / LOCAL_INFLUENCE_RADIUS_DEGREES);

    if (influence <= 0) continue;

    const severityBoost = incident.severity === 'critical'
      ? 1.18
      : incident.severity === 'high'
        ? 1.1
        : incident.severity === 'medium'
          ? 1
          : 0.88;
    const weight = influence * severityBoost;
    weightedRisk += incident.riskScore * weight;
    totalWeight += weight;
    maxRisk = Math.max(maxRisk, incident.riskScore * influence);
  }

  const localScore = totalWeight > 0 ? weightedRisk / totalWeight : 0;
  const baseline = regionRisk > 0 ? regionRisk * 0.18 : 0;

  return Math.max(localScore, maxRisk, baseline);
}

export default function IncidentMap() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  const choroplethLayer = useRef<L.LayerGroup | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<Set<IncidentCategory>>(new Set(categories));
  const [timeRange, setTimeRange] = useState('24h');
  const [showChoropleth, setShowChoropleth] = useState(true);
  const { incidents, alerts, riskScores, stats, lastUpdated, acknowledgeAlert, connectionStatus } = useLiveData(30000);

  const filteredIncidents = useMemo(
    () => filterIncidents(incidents, alerts, selectedCategories, timeRange),
    [incidents, alerts, selectedCategories, timeRange],
  );

  const toggleCategory = (cat: IncidentCategory) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const map = L.map(mapRef.current, {
      center: [33.8547, 35.8623],
      zoom: 8,
      zoomControl: true,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);

    choroplethLayer.current = L.layerGroup().addTo(map);
    markersLayer.current = L.layerGroup().addTo(map);
    mapInstance.current = map;

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  useEffect(() => {
    if (!choroplethLayer.current) return;
    choroplethLayer.current.clearLayers();
    if (!showChoropleth) return;

    const scoreByRegion = new Map<string, number>();
    for (const riskScore of riskScores) {
      scoreByRegion.set(riskScore.region, riskScore.overallScore);
    }

    for (const feature of DISTRICT_FEATURES) {
      const parentRegion = GOVERNORATE_BY_ID.get(feature.properties.parent ?? '') ?? feature.properties.name;
      const districtScore = buildDistrictScore(feature, filteredIncidents, scoreByRegion.get(parentRegion) ?? 0);
      const coords = feature.geometry.coordinates[0].map(
        ([lng, lat]) => [lat, lng] as [number, number],
      );

      const polygon = L.polygon(coords, {
        color: riskStrokeColor(districtScore),
        weight: districtScore >= 70 ? 1.1 : 0.8,
        fillColor: riskToColor(districtScore),
        fillOpacity: riskFillOpacity(districtScore),
        smoothFactor: 1.2,
        dashArray: districtScore >= 55 ? '4 5' : '2 6',
      });

      polygon.bindTooltip(
        `<div style="font-size:12px;font-weight:700;">${feature.properties.name}</div>`
          + `<div style="font-size:11px;color:#cbd5e1;">Governorate: ${parentRegion}</div>`
          + `<div style="font-size:11px;color:#94a3b8;">District risk: ${districtScore.toFixed(1)}/100</div>`,
        { sticky: true, className: 'leaflet-dark-tooltip' },
      );

      polygon.addTo(choroplethLayer.current);
    }
  }, [filteredIncidents, riskScores, showChoropleth]);

  useEffect(() => {
    if (!markersLayer.current) return;
    markersLayer.current.clearLayers();

    filteredIncidents.forEach((incident) => {
      const linkedAlerts = alerts.filter((alert) => alert.linkedIncidents.includes(incident.id));
      const severityRank: Record<AlertSeverity, number> = { emergency: 0, critical: 1, warning: 2, info: 3 };
      const topAlert = linkedAlerts.slice().sort((left, right) => severityRank[left.severity] - severityRank[right.severity])[0];

      const markerRadius = topAlert ? alertSeverityRadius[topAlert.severity] : severityRadius[incident.severity];
      const markerColor = topAlert ? alertSeverityColor[topAlert.severity] : severityColor[incident.severity];

      const ambientGlow = L.circle([incident.location.lat, incident.location.lng], {
        radius: Math.max(2200, incident.riskScore * 55),
        color: markerColor,
        weight: 0,
        fillColor: markerColor,
        fillOpacity: incident.severity === 'critical' ? 0.09 : 0.05,
        interactive: false,
      });
      ambientGlow.addTo(markersLayer.current!);

      const hotspotGlow = L.circle([incident.location.lat, incident.location.lng], {
        radius: Math.max(800, incident.riskScore * 20),
        color: markerColor,
        weight: 0,
        fillColor: markerColor,
        fillOpacity: incident.severity === 'critical' ? 0.16 : 0.09,
        interactive: false,
      });
      hotspotGlow.addTo(markersLayer.current!);

      const marker = L.circleMarker([incident.location.lat, incident.location.lng], {
        radius: markerRadius,
        color: markerColor,
        fillColor: markerColor,
        fillOpacity: 0.6,
        weight: 2,
      });

      const credColor =
        incident.sourceInfo.credibilityScore >= 80 ? '#22C55E'
          : incident.sourceInfo.credibilityScore >= 60 ? '#3B82F6'
            : incident.sourceInfo.credibilityScore >= 40 ? '#F59E0B' : '#EF4444';
      const corrobText = incident.corroboratedBy?.length
        ? `<p style="margin:4px 0 0;color:#22C55E;font-size:11px;">Also: ${incident.corroboratedBy.map((source) => source.name).join(', ')}</p>`
        : '';
      const sourceLink = incident.sourceUrl
        ? `<a href="${incident.sourceUrl}" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:4px;margin-top:6px;color:#3B82F6;font-size:11px;text-decoration:none;">Read full article at ${incident.sourceInfo.name}</a>`
        : '';

      const alertBlock = topAlert
        ? `<div style="margin:8px 0 0;padding:4px 6px;background:rgba(255,255,255,0.05);border-radius:4px;border:1px solid rgba(255,255,255,0.1);">
             <span style="display:block;font-size:11px;text-transform:uppercase;font-weight:800;color:${alertSeverityColor[topAlert.severity]};letter-spacing:0.2px;">
               Alert: ${topAlert.severity}
             </span>
             <span style="display:block;margin-top:2px;font-size:12px;font-weight:700;line-height:1.2;color:#e2e8f0;">
               ${topAlert.title}
             </span>
           </div>`
        : '';

      marker.bindPopup(`
        <div style="min-width:240px;font-size:12px;">
          <p style="font-weight:bold;font-size:14px;margin:0 0 4px;">${incident.title}</p>
          <p style="color:#94a3b8;margin:0 0 4px;">${incident.description}</p>
          <div style="display:flex;gap:8px;margin-top:4px;align-items:center;">
            <span style="text-transform:uppercase;font-weight:bold;color:${severityColor[incident.severity]}">${incident.severity}</span>
            <span>Risk: ${incident.riskScore}</span>
          </div>
          <div style="margin:6px 0;padding:4px 6px;background:rgba(255,255,255,0.05);border-radius:4px;border:1px solid rgba(255,255,255,0.1);">
            <span style="font-weight:600;">Source: ${incident.sourceInfo.name}</span>
            <span style="margin-left:6px;color:${credColor};font-weight:bold;font-size:11px;">${incident.sourceInfo.credibility.toUpperCase()} (${incident.sourceInfo.credibilityScore}/100)</span>
          </div>
          ${corrobText}
          ${sourceLink}
          <p style="margin:4px 0 0;">${incident.region} • ${incident.locationName}</p>
          ${alertBlock}
        </div>
      `);

      marker.addTo(markersLayer.current!);
    });
  }, [filteredIncidents, alerts]);

  const legendItems = [
    { label: 'Low (0-20)', color: 'rgba(34,197,94,0.5)' },
    { label: 'Moderate (20-40)', color: 'rgba(234,179,8,0.55)' },
    { label: 'Elevated (40-55)', color: 'rgba(245,158,11,0.62)' },
    { label: 'High (55-70)', color: 'rgba(249,115,22,0.72)' },
    { label: 'Critical (70+)', color: 'rgba(220,38,38,0.82)' },
  ];

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats, lastUpdated, connectionStatus, acknowledgeAlert }}>
      <div className="flex flex-col h-[calc(100vh-8rem)] gap-4">
        <div className="glass-panel p-3 flex items-center gap-4 flex-wrap">
          <div className="flex gap-1">
            {['1h', '6h', '24h', '7d'].map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-2.5 py-1 text-[10px] font-medium rounded-md uppercase tracking-wider transition-colors ${
                  timeRange === range ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-border" />
          <div className="flex gap-1 flex-wrap">
            {categories.map((category) => (
              <button
                key={category}
                onClick={() => toggleCategory(category)}
                className={`px-2 py-1 text-[10px] rounded-md capitalize transition-colors ${
                  selectedCategories.has(category)
                    ? 'bg-primary/20 text-primary'
                    : 'text-muted-foreground/50 hover:text-muted-foreground bg-secondary/30'
                }`}
              >
                {category.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-border" />
          <button
            onClick={() => setShowChoropleth((value) => !value)}
            className={`px-2.5 py-1 text-[10px] font-medium rounded-md uppercase tracking-wider transition-colors ${
              showChoropleth ? 'bg-warning/20 text-warning' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
            }`}
          >
            Risk Heatmap
          </button>
          <div className="ml-auto text-[10px] text-muted-foreground font-mono-data">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
        </div>

        <div className="flex-1 rounded-lg overflow-hidden border border-border/50 relative">
          <div ref={mapRef} className="h-full w-full" style={{ background: 'hsl(var(--background))' }} />

          {showChoropleth && (
            <div className="absolute bottom-4 left-4 z-[1000] glass-panel p-2.5 text-[10px] space-y-1 pointer-events-none">
              <div className="font-semibold text-foreground mb-1 uppercase tracking-wider">District Risk</div>
              {legendItems.map(({ label, color }) => (
                <div key={label} className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-sm border border-white/20" style={{ background: color }} />
                  <span className="text-muted-foreground">{label}</span>
                </div>
              ))}
              <div className="pt-1 text-[9px] text-muted-foreground/70">
                District shading blends nearby incidents with regional baseline risk.
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
