import { describe, expect, it } from 'vitest';

import { buildLebanonLocationIndex } from '@/lib/lebanonLocations';
import { prepareOfficialFeedPosts } from '@/lib/officialFeedFilters';
import type { OfficialFeedPost } from '@/types/crisis';

const locationIndex = buildLebanonLocationIndex({
  features: [
    {
      properties: {
        'name:en': 'Nabatieh',
        'name:ar': 'النبطية',
        alt_name: 'Houla',
        'alt_name:ar': 'حولا',
      },
    },
    {
      properties: {
        'name:en': 'North Lebanon',
        'name:ar': 'شمال لبنان',
        alt_name: 'Tripoli',
        'alt_name:ar': 'طرابلس',
      },
    },
  ],
});

function buildPost(overrides: Partial<OfficialFeedPost> = {}): OfficialFeedPost {
  return {
    id: 'post-1',
    sourceId: 'source-1',
    isCustom: false,
    platform: 'telegram',
    publisherName: 'LBCI',
    accountLabel: 'LBCI News Wire',
    accountHandle: 'LBCI_NEWS',
    accountUrl: 'https://t.me/LBCI_NEWS',
    postUrl: 'https://t.me/LBCI_NEWS/1',
    content: 'Breaking update from the newsroom',
    signalTags: [],
    matchedKeywords: [],
    primaryKeyword: null,
    sourceInfo: {
      name: 'LBCI',
      type: 'tv',
      credibility: 'verified',
      credibilityScore: 88,
      logoInitials: 'LB',
      url: 'https://t.me/LBCI_NEWS',
      verifiedBy: [],
    },
    publishedAt: '2026-04-16T09:00:00Z',
    category: 'other',
    severity: 'medium',
    region: 'Beirut',
    location: { lat: 33.8938, lng: 35.5018 },
    locationName: 'Lebanon',
    riskScore: 0,
    keywords: [],
    isSafetyRelevant: true,
    aiSignals: null,
    aiScenario: null,
    aiSeverity: null,
    aiConfidence: null,
    aiIsRumor: null,
    ...overrides,
  };
}

describe('prepareOfficialFeedPosts', () => {
  it('prefers backend-resolved location metadata when mapping regions', () => {
    const prepared = prepareOfficialFeedPosts(
      [
        buildPost({
          content: 'General security bulletin without a place in the body',
          locationName: 'Houla',
          region: 'Nabatieh',
        }),
      ],
      locationIndex,
    );

    expect(prepared[0].matchedRegionIds).toContain('nabatieh');
    expect(prepared[0].matchedRegions.map((region) => region.englishName)).toContain('Nabatieh');
  });

  it('falls back to text inference when backend location is still generic', () => {
    const prepared = prepareOfficialFeedPosts(
      [
        buildPost({
          content: 'حادث على طريق طرابلس صباح اليوم',
          locationName: 'Lebanon',
          region: 'Beirut',
        }),
      ],
      locationIndex,
    );

    expect(prepared[0].matchedRegionIds).toContain('north lebanon');
    expect(prepared[0].matchedRegions.map((region) => region.englishName)).toContain('North Lebanon');
  });
});
