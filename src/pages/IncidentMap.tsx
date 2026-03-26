import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import { mockIncidents } from '@/data/mockData';
import 'leaflet/dist/leaflet.css';
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

function MapController() {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
  }, [map]);
  return null;
}

export default function IncidentMap() {
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

  const filteredIncidents = mockIncidents.filter((i) => selectedCategories.has(i.category));

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
          <MapContainer
            center={[33.8547, 35.8623]}
            zoom={8}
            className="h-full w-full"
            style={{ background: 'hsl(var(--background))' }}
          >
            <MapController />
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            />
            {filteredIncidents.map((incident) => (
              <CircleMarker
                key={incident.id}
                center={[incident.location.lat, incident.location.lng]}
                radius={severityRadius[incident.severity]}
                pathOptions={{
                  color: severityColor[incident.severity],
                  fillColor: severityColor[incident.severity],
                  fillOpacity: 0.5,
                  weight: 2,
                }}
              >
                <Popup>
                  <div className="text-xs space-y-1 min-w-[200px]">
                    <p className="font-bold text-sm">{incident.title}</p>
                    <p className="text-muted-foreground">{incident.description}</p>
                    <div className="flex gap-2 pt-1">
                      <span className="uppercase font-bold" style={{ color: severityColor[incident.severity] }}>{incident.severity}</span>
                      <span>Risk: {incident.riskScore}</span>
                    </div>
                    <p>{incident.region} • {incident.locationName}</p>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
      </div>
    </DashboardLayout>
  );
}
