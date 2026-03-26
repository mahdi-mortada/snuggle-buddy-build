import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { mockIncidents } from '@/data/mockData';
import type { IncidentCategory, Severity } from '@/types/crisis';

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

const categories: IncidentCategory[] = ['violence', 'protest', 'natural_disaster', 'infrastructure', 'health', 'terrorism', 'cyber', 'other'];

export default function IncidentMap() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<Set<IncidentCategory>>(new Set(categories));
  const [timeRange, setTimeRange] = useState('24h');

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

    // Fix tile rendering on initial load
    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  // Update markers when filters change
  useEffect(() => {
    if (!markersLayer.current) return;
    markersLayer.current.clearLayers();

    const filtered = mockIncidents.filter((i) => selectedCategories.has(i.category));

    filtered.forEach((incident) => {
      const marker = L.circleMarker([incident.location.lat, incident.location.lng], {
        radius: severityRadius[incident.severity],
        color: severityColor[incident.severity],
        fillColor: severityColor[incident.severity],
        fillOpacity: 0.5,
        weight: 2,
      });

      marker.bindPopup(`
        <div style="min-width:200px;font-size:12px;">
          <p style="font-weight:bold;font-size:14px;margin:0 0 4px;">${incident.title}</p>
          <p style="color:#94a3b8;margin:0 0 4px;">${incident.description}</p>
          <div style="display:flex;gap:8px;margin-top:4px;">
            <span style="text-transform:uppercase;font-weight:bold;color:${severityColor[incident.severity]}">${incident.severity}</span>
            <span>Risk: ${incident.riskScore}</span>
          </div>
          <p style="margin:4px 0 0;">${incident.region} • ${incident.locationName}</p>
        </div>
      `);

      marker.addTo(markersLayer.current!);
    });
  }, [selectedCategories]);

  return (
    <DashboardLayout>
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
        </div>

        {/* Map */}
        <div className="flex-1 rounded-lg overflow-hidden border border-border/50">
          <div ref={mapRef} className="h-full w-full" style={{ background: 'hsl(var(--background))' }} />
        </div>
      </div>
    </DashboardLayout>
  );
}
