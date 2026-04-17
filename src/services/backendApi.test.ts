import { beforeEach, describe, expect, it, vi } from 'vitest';

function jsonResponse(data: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(data), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
}

describe('fetchBackendDashboardSnapshot', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('merges filtered official-feed incidents into the shared live incident snapshot without duplicates', async () => {
    const now = Date.now();
    const liveCreatedAt = new Date(now - 30 * 60 * 1000).toISOString();
    const officialDupPublishedAt = new Date(now - 20 * 60 * 1000).toISOString();
    const officialUniquePublishedAt = new Date(now - 10 * 60 * 1000).toISOString();

    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes('/api/v1/auth/login')) {
        return jsonResponse({
          success: true,
          data: { access_token: 'token-123' },
          error: null,
        });
      }

      if (url.includes('/api/v1/incidents/live?limit=100')) {
        return jsonResponse({
          success: true,
          data: [
            {
              id: 'live-1',
              source: 'news',
              source_id: 'live-1',
              source_url: 'https://news.example/live-1',
              title: 'غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى',
              description: 'غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى',
              raw_text: 'غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى',
              category: 'violence',
              severity: 'critical',
              location: { lat: 33.36, lng: 35.58 },
              location_name: 'Houla',
              region: 'Nabatieh',
              country: 'Lebanon',
              sentiment_score: -0.82,
              risk_score: 92,
              entities: ['Houla', 'Nabatieh'],
              keywords: ['غارة'],
              language: 'ar',
              is_verified: false,
              status: 'new',
              processing_status: 'pending',
              verification_status: 'unverified',
              confidence_score: null,
              reviewed_by: null,
              reviewed_at: null,
              analyst_notes: null,
              metadata: {},
              source_info: {
                name: 'LBCI',
                type: 'tv',
                credibility: 'verified',
                credibilityScore: 88,
                logoInitials: 'LB',
                url: 'https://news.example/live-1',
                verifiedBy: [],
              },
              created_at: liveCreatedAt,
              updated_at: liveCreatedAt,
            },
          ],
          error: null,
        });
      }

      if (url.includes('/api/v1/official-feeds?limit=50')) {
        return jsonResponse({
          success: true,
          data: [
            {
              id: 'official-dup',
              platform: 'telegram',
              publisher_name: 'LBCI',
              account_label: 'LBCI News Wire',
              account_handle: 'LBCI_NEWS',
              account_url: 'https://t.me/LBCI_NEWS',
              post_url: 'https://t.me/LBCI_NEWS/100',
              content: 'غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى',
              signal_tags: ['غارة'],
              source_info: {
                name: 'LBCI',
                type: 'tv',
                credibility: 'verified',
                credibilityScore: 88,
                logoInitials: 'LB',
                url: 'https://t.me/LBCI_NEWS',
                verifiedBy: [],
              },
              published_at: officialDupPublishedAt,
              is_safety_relevant: true,
              category: 'violence',
              severity: 'critical',
              region: 'Nabatieh',
              location_name: 'Houla',
              location: { lat: 33.36, lng: 35.58 },
              risk_score: 93,
              keywords: ['غارة'],
            },
            {
              id: 'official-unique',
              platform: 'telegram',
              publisher_name: 'MTV Lebanon',
              account_label: 'MTV Lebanon News',
              account_handle: 'MTVLebanoNews',
              account_url: 'https://t.me/MTVLebanoNews',
              post_url: 'https://t.me/MTVLebanoNews/200',
              content: 'حادث سير على أوتوستراد الزهراني العدوسية في جنوب لبنان ووقوع جريحين',
              signal_tags: ['حادث'],
              source_info: {
                name: 'MTV Lebanon',
                type: 'tv',
                credibility: 'high',
                credibilityScore: 84,
                logoInitials: 'MT',
                url: 'https://t.me/MTVLebanoNews',
                verifiedBy: [],
              },
              published_at: officialUniquePublishedAt,
              is_safety_relevant: true,
              category: 'violence',
              severity: 'high',
              region: 'South Lebanon',
              location_name: 'South Lebanon',
              location: { lat: 33.2721, lng: 35.2033 },
              risk_score: 78,
              keywords: ['حادث', 'جريحين'],
            },
          ],
          error: null,
        });
      }

      if (
        url.includes('/api/v1/dashboard/overview') ||
        url.includes('/api/v1/incidents?page=1&per_page=100') ||
        url.includes('/api/v1/alerts') ||
        url.includes('/api/v1/risk/current') ||
        url.includes('/api/v1/dashboard/trends')
      ) {
        return jsonResponse({
          success: true,
          data: url.includes('/api/v1/incidents?page=1&per_page=100')
            ? { items: [], page: 1, per_page: 100, total: 0 }
            : url.includes('/api/v1/dashboard/overview')
              ? { total_incidents_24h: 0, active_alerts: 0, avg_risk_score: 0, top_risk_region: 'Unknown' }
              : [],
          error: null,
        });
      }

      return Promise.reject(new Error(`Unexpected fetch URL: ${url}`));
    });

    vi.stubGlobal('fetch', fetchMock);

    const { fetchBackendDashboardSnapshot } = await import('@/services/backendApi');
    const snapshot = await fetchBackendDashboardSnapshot();

    expect(snapshot.incidents).toHaveLength(2);
    expect(snapshot.incidents.filter((incident) => incident.title === 'غارة إسرائيلية على بلدة حولا جنوب لبنان وسقوط جرحى')).toHaveLength(1);
    expect(snapshot.incidents.some((incident) => incident.source === 'official_feed' && incident.locationName === 'South Lebanon')).toBe(true);
    expect(snapshot.stats.totalIncidents24h).toBe(2);
  });
});
