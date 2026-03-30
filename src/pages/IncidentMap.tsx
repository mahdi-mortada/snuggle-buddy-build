import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useLiveData } from '@/hooks/useLiveData';
import type { AlertSeverity, IncidentCategory, Severity } from '@/types/crisis';

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

const categories: IncidentCategory[] = ['violence', 'protest', 'natural_disaster', 'infrastructure', 'health', 'terrorism', 'cyber', 'other'];

export default function IncidentMap() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<Set<IncidentCategory>>(new Set(categories));
  const [timeRange, setTimeRange] = useState('24h');
  const { incidents, alerts, stats, lastUpdated } = useLiveData(30000);

  const toggleCategory = (cat: IncidentCategory) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  // Initialize map
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

    markersLayer.current = L.layerGroup().addTo(map);
    mapInstance.current = map;

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  // Update markers when incidents or filters change
  useEffect(() => {
    if (!markersLayer.current) return;
    markersLayer.current.clearLayers();

    const timeMs =
      timeRange === '1h'
        ? 1 * 3600 * 1000
        : timeRange === '6h'
          ? 6 * 3600 * 1000
          : timeRange === '7d'
            ? 7 * 24 * 3600 * 1000
            : 24 * 3600 * 1000;

    const alertIncidentIds = new Set(alerts.flatMap((a) => a.linkedIncidents));
    const hasAlertLinks = alertIncidentIds.size > 0;
    const cutoff = Date.now() - timeMs;

    const filtered = incidents.filter((i) => {
      const createdAt = new Date(i.createdAt).getTime();
      const withinTime = Number.isFinite(createdAt) ? createdAt >= cutoff : true;
      const categoryOk = selectedCategories.has(i.category);
      const alertOk = !hasAlertLinks || alertIncidentIds.has(i.id);
      return withinTime && categoryOk && alertOk;
    });

    filtered.forEach((incident) => {
      const linkedAlerts = alerts.filter((a) => a.linkedIncidents.includes(incident.id));
      const severityRank: Record<AlertSeverity, number> = { emergency: 0, critical: 1, warning: 2, info: 3 };
      const topAlert = linkedAlerts.slice().sort((a, b) => severityRank[a.severity] - severityRank[b.severity])[0];

      const markerRadius = topAlert ? alertSeverityRadius[topAlert.severity] : severityRadius[incident.severity];
      const markerColor = topAlert ? alertSeverityColor[topAlert.severity] : severityColor[incident.severity];

      const marker = L.circleMarker([incident.location.lat, incident.location.lng], {
        radius: markerRadius,
        color: markerColor,
        fillColor: markerColor,
        fillOpacity: 0.5,
        weight: 2,
      });

      const credColor = incident.sourceInfo.credibilityScore >= 80 ? '#22C55E' : incident.sourceInfo.credibilityScore >= 60 ? '#3B82F6' : incident.sourceInfo.credibilityScore >= 40 ? '#F59E0B' : '#EF4444';
      const corrobText = incident.corroboratedBy?.length ? `<p style="margin:4px 0 0;color:#22C55E;font-size:11px;">✓ Also: ${incident.corroboratedBy.map(s => s.name).join(', ')}</p>` : '';
      const sourceLink = incident.sourceUrl
        ? `<a href="${incident.sourceUrl}" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:4px;margin-top:6px;color:#3B82F6;font-size:11px;text-decoration:none;">🔗 Read full article at ${incident.sourceInfo.name}</a>`
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
            <span style="font-weight:600;">📰 ${incident.sourceInfo.name}</span>
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
  }, [selectedCategories, incidents, alerts, timeRange]);

  return (
    <DashboardLayout liveData={{ incidents, alerts, stats, lastUpdated }}>
      <div className="flex flex-col h-[calc(100vh-8rem)] gap-4">
        {/* Controls */}
        <div className="glass-panel p-3 flex items-center gap-4 flex-wrap">
          <div className="flex gap-1">
            {['1h', '6h', '24h', '7d'].map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-2.5 py-1 text-[10px] font-medium rounded-md uppercase tracking-wider transition-colors ${
                  timeRange === r ? 'bg-primary/20 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-border" />
          <div className="flex gap-1 flex-wrap">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => toggleCategory(cat)}
                className={`px-2 py-1 text-[10px] rounded-md capitalize transition-colors ${
                  selectedCategories.has(cat)
                    ? 'bg-primary/20 text-primary'
                    : 'text-muted-foreground/50 hover:text-muted-foreground bg-secondary/30'
                }`}
              >
                {cat.replace('_', ' ')}
              </button>
            ))}
          </div>
          <div className="ml-auto text-[10px] text-muted-foreground font-mono-data">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </div>
        </div>

        {/* Map */}
        <div className="flex-1 rounded-lg overflow-hidden border border-border/50">
          <div ref={mapRef} className="h-full w-full" style={{ background: 'hsl(var(--background))' }} />
        </div>
      </div>
    </DashboardLayout>
  );
}
