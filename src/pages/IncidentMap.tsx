import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useLiveData } from '@/hooks/useLiveData';
import { resolveSourceUrl } from '@/lib/sourceLink';
import type { Incident, IncidentCategory, OfficialFeedPost } from '@/types/crisis';
import { fetchBackendLiveIncidents, fetchBackendOfficialFeedPosts } from '@/services/backendApi';

type LebanonFeatureProperties = {
  GID_3?: string;
  NAME_1?: string;
  NAME_2?: string;
  NAME_3?: string;
};

type LebanonGeoJson = GeoJSON.FeatureCollection<
  GeoJSON.Polygon | GeoJSON.MultiPolygon,
  LebanonFeatureProperties
>;

type MarkerKind = 'violence' | 'armed_conflict' | 'terrorism' | 'protest' | 'natural_disaster' | 'fire' | 'infrastructure' | 'health' | 'cyber' | 'drone' | 'crime' | 'default';

type MarkerEvent = {
  id: string;
  type: 'incident' | 'telegram';
  text: string;
  title: string;
  description: string;
  location: string;
  sourceUrl: string | null;
  sourceType: 'incident' | 'telegram';
  timestamp: number;
  lat: number;
  lng: number;
  kind: MarkerKind;
};

type OSMRawElement = {
  lat?: number;
  lon?: number;
  tags?: Record<string, unknown>;
};

type OSMRawFeature = {
  geometry?: {
    type?: string;
    coordinates?: number[];
  };
  properties?: Record<string, unknown>;
};

type OSMRawData = {
  elements?: OSMRawElement[];
  features?: OSMRawFeature[];
};

type OSMAlias = {
  raw: string;
  normalized: string;
  tokens: string[];
  script: 'ar' | 'latin';
  priority: number;
};

type OSMLocation = {
  label: string;
  lat: number;
  lng: number;
  aliases: OSMAlias[];
};

const categories: IncidentCategory[] = ['violence', 'protest', 'natural_disaster', 'infrastructure', 'health', 'terrorism', 'cyber', 'armed_conflict', 'other'];

const INCIDENT_MAP_DEBUG = true;
const FEED_WINDOW_MS = 48 * 60 * 60 * 1000;

const markerKindStyles: Record<MarkerKind, { emoji: string; color: string; label: string }> = {
  violence:           { emoji: '\u2694\uFE0F', color: '#ef4444', label: 'Violence' },
  armed_conflict:     { emoji: '\u{1F4A5}', color: '#dc2626', label: 'Armed Conflict' },
  terrorism:          { emoji: '\u{1F4A3}', color: '#b91c1c', label: 'Terrorism' },
  protest:            { emoji: '\u270A', color: '#f59e0b', label: 'Protest' },
  natural_disaster:   { emoji: '\u{1F30A}', color: '#06b6d4', label: 'Natural Disaster' },
  fire:               { emoji: '\u{1F525}', color: '#f97316', label: 'Fire' },
  infrastructure:     { emoji: '\u26A1', color: '#a855f7', label: 'Infrastructure' },
  health:             { emoji: '\u{1F3E5}', color: '#10b981', label: 'Health' },
  cyber:              { emoji: '\u{1F4BB}', color: '#6366f1', label: 'Cyber' },
  drone:              { emoji: '\u{1F6E9}\uFE0F', color: '#e11d48', label: 'Drone/UAV' },
  crime:              { emoji: '\u{1F6A8}', color: '#f59e0b', label: 'Crime' },
  default:            { emoji: '\u{1F4CD}', color: '#3b82f6', label: 'Other' },
};

const markerIcons: Record<MarkerKind, L.DivIcon> = Object.fromEntries(
  Object.keys(markerKindStyles).map((kind) => [kind, createMarkerIcon(kind as MarkerKind)])
) as Record<MarkerKind, L.DivIcon>;

function createMarkerIcon(kind: MarkerKind) {
  const style = markerKindStyles[kind];
  return L.divIcon({
    className: '',
    html: `<div style="width:26px;height:26px;border-radius:999px;background:${style.color};display:flex;align-items:center;justify-content:center;border:2px solid rgba(15,23,42,0.95);font-size:14px;box-shadow:0 0 0 2px rgba(15,23,42,0.35);">${style.emoji}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -14],
  });
}

const hasArabicChars = (value: string) => /[\u0600-\u06FF]/.test(value);

const normalizeArabicText = (value: string | undefined) => {
  if (!value) return '';

  const base = value
    .normalize('NFKD')
    .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g, '')
    .replace(/[\u0640]/g, '')
    .replace(/[Ø£Ø¥Ø¢Ù±]/g, 'Ø§')
    .replace(/[Ø¤]/g, 'Ùˆ')
    .replace(/[Ø¦]/g, 'ÙŠ')
    .replace(/[Ù‰]/g, 'ÙŠ')
    .replace(/[Ø©]/g, 'Ù‡')
    .replace(/[^\u0621-\u064A0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (!base) return '';

  return base
    .split(' ')
    .map((token) => {
      const stripped = token.startsWith('Ø§Ù„') && token.length > 2 ? token.slice(2) : token;
      return stripped;
    })
    .filter(Boolean)
    .join(' ')
    .trim();
};

const normalizeLatinText = (value: string | undefined) => {
  if (!value) return '';

  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
};

const normalizeArabicWord = (word: string) => {
  return word
    .normalize('NFKD')
    .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g, '')
    .replace(/[\u0640]/g, '')
    .replace(/[^\u0621-\u064A0-9]/g, '')
    .replace(/^\u0627\u0644/u, '')
    .replace(/^\u0628/u, '')
    .replace(/^\u0648/u, '')
    .trim();
};

const normalizeLatinWord = (word: string) => {
  return word
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]/g, '')
    .trim();
};

const tokenizeArabicWords = (text: string | undefined) => {
  if (!text) return [] as string[];
  return text
    .split(/\s+/)
    .map((word) => normalizeArabicWord(word))
    .filter((word) => word.length > 0);
};

const tokenizeLatinWords = (text: string | undefined) => {
  if (!text) return [] as string[];
  return text
    .split(/\s+/)
    .map((word) => normalizeLatinWord(word))
    .filter((word) => word.length > 0);
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const isFiniteCoordinate = (lat: number, lng: number) =>
  Number.isFinite(lat) && Number.isFinite(lng) && lat >= 33.0 && lat <= 34.9 && lng >= 35.0 && lng <= 36.9;

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const extractAliasesFromTags = (tags?: Record<string, unknown>): OSMAlias[] => {
  if (!tags) return [];

  const aliases: OSMAlias[] = [];
  const pushAlias = (rawValue: unknown, priority: number) => {
    if (typeof rawValue !== 'string') return;
    const raw = rawValue.trim();
    if (!raw) return;

    const script = hasArabicChars(raw) ? 'ar' : 'latin';
    const tokens = script === 'ar' ? tokenizeArabicWords(raw) : tokenizeLatinWords(raw);
    if (tokens.length === 0) return;
    const normalized = tokens.join(' ');

    aliases.push({ raw, normalized, tokens, script, priority });
  };

  // Primary/fallback matching exactly as requested.
  pushAlias(tags['name:ar'], 0);
  pushAlias(tags['name:en'], 1);

  const seen = new Set<string>();
  return aliases.filter((alias) => {
    const key = `${alias.script}:${alias.normalized}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const hasExactTokenMatch = (haystackWords: string[], needleWords: string[]) => {
  if (haystackWords.length === 0 || needleWords.length === 0) {
    return false;
  }

  if (needleWords.length === 1) {
    const needle = needleWords[0];
    return haystackWords.some((word) => word === needle);
  }

  for (let i = 0; i <= haystackWords.length - needleWords.length; i += 1) {
    let isMatch = true;
    for (let j = 0; j < needleWords.length; j += 1) {
      if (haystackWords[i + j] !== needleWords[j]) {
        isMatch = false;
        break;
      }
    }
    if (isMatch) {
      return true;
    }
  }

  return false;
};

const buildOsmLocationDatabase = (raw: OSMRawData): OSMLocation[] => {
  const registry = new Map<string, OSMLocation>();

  const registerLocation = (lat: number, lng: number, aliases: OSMAlias[]) => {
    if (!isFiniteCoordinate(lat, lng)) return;
    if (aliases.length === 0) return;

    const sortedAliases = [...aliases].sort((left, right) => left.priority - right.priority);
    const primaryAlias = sortedAliases[0];
    const key = `${lat.toFixed(5)}:${lng.toFixed(5)}:${primaryAlias.normalized}`;

    if (!registry.has(key)) {
      const preferredLabel = sortedAliases.find((alias) => alias.script === 'ar')?.raw ?? primaryAlias.raw;
      registry.set(key, {
        label: preferredLabel,
        lat,
        lng,
        aliases: sortedAliases,
      });
      return;
    }

    const existing = registry.get(key);
    if (!existing) return;

    const seen = new Set(existing.aliases.map((alias) => `${alias.script}:${alias.normalized}`));
    for (const alias of sortedAliases) {
      const aliasKey = `${alias.script}:${alias.normalized}`;
      if (seen.has(aliasKey)) continue;
      existing.aliases.push(alias);
      seen.add(aliasKey);
    }
  };

  if (Array.isArray(raw.elements)) {
    for (const element of raw.elements) {
      const lat = toNumber(element.lat);
      const lng = toNumber(element.lon);
      if (lat === null || lng === null) continue;

      const aliases = extractAliasesFromTags(element.tags);
      registerLocation(lat, lng, aliases);
    }
  }

  if (Array.isArray(raw.features)) {
    for (const feature of raw.features) {
      if (feature.geometry?.type !== 'Point' || !Array.isArray(feature.geometry.coordinates)) continue;
      const lng = toNumber(feature.geometry.coordinates[0]);
      const lat = toNumber(feature.geometry.coordinates[1]);
      if (lat === null || lng === null) continue;

      const aliases = extractAliasesFromTags(feature.properties);
      registerLocation(lat, lng, aliases);
    }
  }

  return Array.from(registry.values());
};

const findLocationByReverseGeoJsonScan = (text: string, locations: OSMLocation[]) => {
  const arabicWords = tokenizeArabicWords(text);
  const latinWords = tokenizeLatinWords(text);

  if (arabicWords.length === 0 && latinWords.length === 0) {
    return null;
  }

  let bestMatch: { location: OSMLocation; alias: OSMAlias; score: number } | null = null;

  for (const location of locations) {
    for (const alias of location.aliases) {
      if (alias.tokens.length === 0) continue;

      const haystackTokens = alias.script === 'ar' ? arabicWords : latinWords;
      if (haystackTokens.length === 0) continue;
      if (!hasExactTokenMatch(haystackTokens, alias.tokens)) continue;

      const score = (alias.script === 'ar' ? 5000 : 4000) - alias.priority * 100 + alias.normalized.length;
      if (!bestMatch || score > bestMatch.score) {
        bestMatch = { location, alias, score };
      }
    }
  }

  return bestMatch;
};

/** Map a backend category string to a MarkerKind. */
const categoryToMarkerKind = (category: string | undefined): MarkerKind | null => {
  if (!category) return null;
  const map: Record<string, MarkerKind> = {
    violence: 'violence',
    armed_conflict: 'armed_conflict',
    terrorism: 'terrorism',
    protest: 'protest',
    natural_disaster: 'natural_disaster',
    infrastructure: 'infrastructure',
    health: 'health',
    cyber: 'cyber',
  };
  return map[category] ?? null;
};

/** Refine marker kind by scanning the full text for sub-category keywords.
 *  E.g. a "violence" post about a drone gets the drone icon instead of generic violence. */
const refineKindByText = (baseKind: MarkerKind, text: string): MarkerKind => {
  const lower = text.toLowerCase();

  // Drone/UAV — very common in Lebanese alert channels
  if (lower.includes('drone') || lower.includes('uav') || /مسير/.test(text) || /طائرة/.test(text) || lower.includes('#مسير')) {
    return 'drone';
  }
  // Fire
  if (lower.includes('fire') || lower.includes('blaze') || lower.includes('wildfire') || /حريق/.test(text)) {
    return 'fire';
  }
  return baseKind;
};

const inferMarkerKind = (incident: Incident): MarkerKind => {
  // Use backend-assigned category
  const fromCategory = categoryToMarkerKind(incident.category);
  const base = fromCategory ?? 'default';
  // Refine with text scan for sub-categories (drone, fire)
  const fullText = (incident.title || '') + ' ' + (incident.description || '');
  return refineKindByText(base, fullText);
};

const inferMarkerKindFromCategory = (category: string | undefined, text: string): MarkerKind => {
  const fromCategory = categoryToMarkerKind(category);
  const base = fromCategory ?? 'default';
  return refineKindByText(base, text);
};

const formatIncidentTime = (timestamp: number) => {
  if (!Number.isFinite(timestamp)) return 'Unknown time';
  return new Date(timestamp).toLocaleString();
};

export default function IncidentMap() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const regionsLayer = useRef<L.GeoJSON | null>(null);
  const markersLayer = useRef<L.LayerGroup | null>(null);
  const hasFittedBounds = useRef(false);

  const [selectedCategories, setSelectedCategories] = useState<Set<IncidentCategory>>(new Set(categories));
  const [timeRange, setTimeRange] = useState('48h');
  const [geoJsonData, setGeoJsonData] = useState<LebanonGeoJson | null>(null);
  const [osmLocations, setOsmLocations] = useState<OSMLocation[]>([]);
  const [liveIncidents, setLiveIncidents] = useState<Incident[]>([]);
  const [telegramFeeds, setTelegramFeeds] = useState<OfficialFeedPost[]>([]);
  const [mapFeedLoading, setMapFeedLoading] = useState(true);
  const [mapFeedError, setMapFeedError] = useState<string | null>(null);
  const isFetchingMapFeedRef = useRef(false);

  const { alerts, stats, lastUpdated, connectionStatus } = useLiveData(30000);

  const loadMapFeed = useCallback(async (showLoading = false) => {
    if (isFetchingMapFeedRef.current) return;
    isFetchingMapFeedRef.current = true;

    if (showLoading) {
      setMapFeedLoading(true);
    }

    try {
      const [nextIncidents, nextTelegramFeeds] = await Promise.all([
        fetchBackendLiveIncidents(100),
        fetchBackendOfficialFeedPosts(50),
      ]);
      setLiveIncidents(nextIncidents);
      setTelegramFeeds(nextTelegramFeeds);
      setMapFeedError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load map feed.';
      setMapFeedError(message);
    } finally {
      if (showLoading) {
        setMapFeedLoading(false);
      }
      isFetchingMapFeedRef.current = false;
    }
  }, []);

  useEffect(() => {
    void loadMapFeed(true);
  }, [loadMapFeed]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadMapFeed(false);
    }, 10000);

    return () => {
      window.clearInterval(timer);
    };
  }, [loadMapFeed]);

  const cutoffTimestamp = useMemo(() => {
    const timeMs =
      timeRange === '1h'
        ? 1 * 3600 * 1000
        : timeRange === '6h'
          ? 6 * 3600 * 1000
          : timeRange === '48h'
            ? 48 * 3600 * 1000
          : timeRange === '7d'
            ? 7 * 24 * 3600 * 1000
            : 24 * 3600 * 1000;
    const selectedCutoff = Date.now() - timeMs;
    const feedWindowCutoff = Date.now() - FEED_WINDOW_MS;
    return Math.max(selectedCutoff, feedWindowCutoff);
  }, [timeRange]);

  const filteredIncidents = useMemo(() => {
    const cutoff = cutoffTimestamp;

    return liveIncidents.filter((incident) => {
      const createdAt = new Date(incident.createdAt).getTime();
      const withinTime = Number.isFinite(createdAt) ? createdAt >= cutoff : false;
      const categoryOk = selectedCategories.has(incident.category);
      return withinTime && categoryOk;
    });
  }, [liveIncidents, selectedCategories, cutoffTimestamp]);

  const filteredTelegramFeeds = useMemo(() => {
    const cutoff = cutoffTimestamp;
    return telegramFeeds.filter((feed) => {
      const publishedAt = new Date(feed.publishedAt).getTime();
      return Number.isFinite(publishedAt) ? publishedAt >= cutoff : false;
    });
  }, [telegramFeeds, cutoffTimestamp]);

  const markerEvents = useMemo(() => {
    const events: MarkerEvent[] = [];

    for (const incident of filteredIncidents) {
      const incidentRawText = (incident as Incident & { rawText?: string; raw_text?: string }).rawText
        ?? (incident as Incident & { rawText?: string; raw_text?: string }).raw_text
        ?? '';
      const incidentText = `${incident.title || ''} ${incident.description || ''} ${incidentRawText || ''}`.trim();
      const sourceUrl = resolveSourceUrl(incident);

      // 1. Prefer backend-provided coordinates (already validated by NLP pipeline)
      let lat: number | null = null;
      let lng: number | null = null;
      let locationLabel = incident.locationName || incident.region || 'Lebanon';

      if (incident.location && isFiniteCoordinate(incident.location.lat, incident.location.lng)) {
        lat = incident.location.lat;
        lng = incident.location.lng;
      }

      // 2. Fall back to OSM text matching only if backend coordinates missing/invalid
      if (lat === null || lng === null) {
        const matchResult = findLocationByReverseGeoJsonScan(incidentText.toLowerCase(), osmLocations);
        if (matchResult) {
          lat = matchResult.location.lat;
          lng = matchResult.location.lng;
          locationLabel = matchResult.alias.raw;
        }
      }

      // Skip if we still have no valid Lebanon coordinates
      if (lat === null || lng === null) {
        if (INCIDENT_MAP_DEBUG) {
          console.log('[IncidentMap] skipped incident (no Lebanon coordinates)', { title: incident.title });
        }
        continue;
      }

      events.push({
        id: `incident-${incident.id}`,
        type: 'incident',
        text: incidentText,
        title: incident.title,
        description: incident.description,
        location: locationLabel,
        sourceUrl,
        sourceType: 'incident',
        timestamp: new Date(incident.createdAt).getTime(),
        lat,
        lng,
        kind: inferMarkerKind(incident),
      });
    }

    for (const feed of filteredTelegramFeeds) {
      const text = (feed.content || '').trim();
      if (!text) continue;
      const sourceUrl = resolveSourceUrl(feed);

      // 1. Prefer backend-provided coordinates
      let lat: number | null = null;
      let lng: number | null = null;
      let locationLabel = feed.locationName || feed.region || 'Lebanon';

      if (feed.location && isFiniteCoordinate(feed.location.lat, feed.location.lng)) {
        lat = feed.location.lat;
        lng = feed.location.lng;
      }

      // 2. Fall back to OSM text matching
      if (lat === null || lng === null) {
        const matchResult = findLocationByReverseGeoJsonScan(text.toLowerCase(), osmLocations);
        if (matchResult) {
          lat = matchResult.location.lat;
          lng = matchResult.location.lng;
          locationLabel = matchResult.alias.raw;
        }
      }

      if (lat === null || lng === null) {
        if (INCIDENT_MAP_DEBUG) {
          console.log('[IncidentMap] skipped telegram post (no Lebanon coordinates)', { text: text.slice(0, 60) });
        }
        continue;
      }

      events.push({
        id: `telegram-${feed.id}`,
        type: 'telegram',
        text,
        title: feed.accountLabel || feed.publisherName || 'Telegram Feed',
        description: text,
        location: locationLabel,
        sourceUrl,
        sourceType: 'telegram',
        timestamp: new Date(feed.publishedAt).getTime(),
        lat,
        lng,
        kind: inferMarkerKindFromCategory(feed.category, text),
      });
    }

    events.sort((left, right) => right.timestamp - left.timestamp);
    return events;
  }, [filteredIncidents, filteredTelegramFeeds, osmLocations]);

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

    markersLayer.current = L.layerGroup().addTo(map);
    mapInstance.current = map;

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      regionsLayer.current = null;
      markersLayer.current = null;
      hasFittedBounds.current = false;
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    fetch('/maps/gadm41_LBN_3.geojson')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load GeoJSON (${response.status})`);
        }
        return response.json() as Promise<LebanonGeoJson>;
      })
      .then((data) => {
        if (isMounted) {
          setGeoJsonData(data);
        }
      })
      .catch((error) => {
        console.error('Unable to load Lebanon GeoJSON regions:', error);
      });

    fetch('/maps/osm-export.geojson')
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load OSM locations (${response.status})`);
        }
        return response.json() as Promise<OSMRawData>;
      })
      .then((raw) => {
        if (!isMounted) return;
        const transformed = buildOsmLocationDatabase(raw);
        setOsmLocations(transformed);
      })
      .catch((error) => {
        console.error('Unable to load OSM location database:', error);
        if (isMounted) {
          setOsmLocations([]);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !geoJsonData) return;

    if (markersLayer.current) {
      markersLayer.current.clearLayers();
    }

    if (!regionsLayer.current) {
      const regionLayer = L.geoJSON(geoJsonData, {
        style: {
          color: '#334155',
          weight: 0.5,
          opacity: 0.45,
          fillColor: '#1e293b',
          fillOpacity: 0.06,
        },
        interactive: false,
      }).addTo(mapInstance.current);
      regionsLayer.current = regionLayer;
    }

    markerEvents.forEach((eventItem) => {
      if (!markersLayer.current) return;
      const popupButtonId = `source-btn-${eventItem.id.replace(/[^a-zA-Z0-9_-]/g, '-')}`;
      const sourceButtonHtml = eventItem.sourceUrl
        ? `<button id="${popupButtonId}" type="button" style="margin-top:8px;display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(59,130,246,0.3);background:rgba(59,130,246,0.15);color:#93c5fd;border-radius:6px;padding:4px 8px;font-size:11px;cursor:pointer;">View Source</button>`
        : '';

      const marker = L.marker([eventItem.lat, eventItem.lng], {
        icon: markerIcons[eventItem.kind],
      });

      const kindStyle = markerKindStyles[eventItem.kind];
      marker.bindPopup(
        `<div style="min-width:280px;">
           <p style="margin:0 0 6px;font-weight:700;font-size:14px;line-height:1.4;">${escapeHtml(eventItem.title)}</p>
           <p style="margin:0 0 8px;color:#cbd5e1;font-size:12px;line-height:1.5;">${escapeHtml(eventItem.text || eventItem.description || '')}</p>
           <p style="margin:0;font-size:11px;color:#94a3b8;">
             <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${kindStyle.color};margin-right:4px;vertical-align:middle;"></span>
             ${escapeHtml(kindStyle.label)} &middot; ${escapeHtml(eventItem.type)}
           </p>
           <p style="margin:4px 0 0;font-size:11px;color:#94a3b8;">Location: ${escapeHtml(eventItem.location)}</p>
           <p style="margin:4px 0 0;font-size:11px;color:#94a3b8;">Time: ${escapeHtml(formatIncidentTime(eventItem.timestamp))}</p>
           ${sourceButtonHtml}
          </div>`,
        { maxWidth: 340 }
      );

      if (eventItem.sourceUrl) {
        marker.on('popupopen', () => {
          const button = document.getElementById(popupButtonId);
          if (!(button instanceof HTMLButtonElement)) return;
          if (button.dataset.bound === 'true') return;
          button.dataset.bound = 'true';
          button.addEventListener('click', () => {
            window.open(eventItem.sourceUrl as string, '_blank', 'noopener,noreferrer');
          });
        });
      }

      marker.addTo(markersLayer.current);
    });

    if (!hasFittedBounds.current) {
      const bounds = regionsLayer.current.getBounds();
      if (bounds.isValid()) {
        mapInstance.current.fitBounds(bounds.pad(0.02), { animate: false });
        hasFittedBounds.current = true;
      }
    }
  }, [geoJsonData, markerEvents]);

  return (
    <DashboardLayout liveData={{ incidents: liveIncidents, alerts, stats, lastUpdated, connectionStatus }}>
      <div className="flex flex-col h-[calc(100vh-8rem)] gap-4">
        {/* Controls */}
        <div className="glass-panel p-3 flex items-center gap-4 flex-wrap">
          <div className="flex gap-1">
            {['1h', '6h', '24h', '48h', '7d'].map((r) => (
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
            {mapFeedLoading ? 'Loading map feed...' : mapFeedError ? `Feed error: ${mapFeedError}` : `Markers: ${markerEvents.length} (incidents: ${filteredIncidents.length}, telegram: ${filteredTelegramFeeds.length})`}
          </div>
          <div className="text-[10px] text-muted-foreground font-mono-data">
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
