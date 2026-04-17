import type { OfficialFeedPost } from '@/types/crisis';
import { inferRegionIdsFromText, normalizeArabicText, normalizeLatinText, type LebanonLocationIndex, type RegionOption } from '@/lib/lebanonLocations';

export type OfficialFeedFilterState = {
  selectedSources: string[];
  selectedRegionIds: string[];
  keyword: string;
};

export type FilterOption = {
  id: string;
  label: string;
  searchText?: string;
};

export type PreparedOfficialFeedPost = {
  post: OfficialFeedPost;
  sourceId: string;
  sourceLabel: string;
  searchTextLatin: string;
  searchTextArabic: string;
  matchedRegionIds: string[];
  matchedRegions: RegionOption[];
};

export function buildSourceOptions(posts: OfficialFeedPost[]): FilterOption[] {
  const options = new Map<string, FilterOption>();

  for (const post of posts) {
    const sourceLabel = post.publisherName || post.accountLabel || post.sourceInfo.name;
    const sourceId = post.sourceId || normalizeLatinText(sourceLabel);
    if (!sourceId || options.has(sourceId)) continue;
    options.set(sourceId, {
      id: sourceId,
      label: sourceLabel,
      searchText: `${sourceLabel} ${post.accountLabel} ${post.accountHandle}`,
    });
  }

  return Array.from(options.values()).sort((left, right) => left.label.localeCompare(right.label));
}

export function prepareOfficialFeedPosts(
  posts: OfficialFeedPost[],
  locationIndex: LebanonLocationIndex | null,
): PreparedOfficialFeedPost[] {
  return posts.map((post) => {
    const sourceLabel = post.publisherName || post.accountLabel || post.sourceInfo.name;
    const sourceId = post.sourceId || normalizeLatinText(sourceLabel);
    const rawSearchText = [
      post.publisherName,
      post.accountLabel,
      post.accountHandle,
      post.locationName,
      post.region,
      post.content,
      ...(post.signalTags ?? []),
      ...(post.matchedKeywords ?? []),
    ]
      .filter(Boolean)
      .join(' ');

    // Prefer the backend-resolved location/region as the canonical filter source.
    // Fall back to raw text inference only when the backend payload is too generic
    // to map to a region option (for example, unresolved legacy payloads).
    const backendResolvedLocationText = [post.locationName, post.region]
      .filter(Boolean)
      .join(' ');
    const matchedRegionIds = hasSpecificBackendLocation(post.locationName)
      ? inferRegionIdsFromText(backendResolvedLocationText, locationIndex)
      : [];
    const fallbackRegionIds = matchedRegionIds.length > 0
      ? matchedRegionIds
      : inferRegionIdsFromText(rawSearchText, locationIndex);
    const matchedRegions = fallbackRegionIds
      .map((regionId) => {
        const region = locationIndex?.regionLookup.get(regionId);
        if (!region) return null;

        return {
          id: region.id,
          label: region.label,
          englishName: region.englishName,
          arabicName: region.arabicName,
          searchText: region.searchText,
        } satisfies RegionOption;
      })
      .filter((region): region is RegionOption => region !== null);

    return {
      post,
      sourceId,
      sourceLabel,
      searchTextLatin: normalizeLatinText(rawSearchText),
      searchTextArabic: normalizeArabicText(rawSearchText),
      matchedRegionIds: fallbackRegionIds,
      matchedRegions,
    };
  });
}

function hasSpecificBackendLocation(locationName: string): boolean {
  const latinLocation = normalizeLatinText(locationName);
  const arabicLocation = normalizeArabicText(locationName);
  return Boolean(locationName.trim()) && latinLocation !== 'lebanon' && arabicLocation !== 'لبنان';
}

export function buildRegionOptions(preparedPosts: PreparedOfficialFeedPost[]): FilterOption[] {
  const options = new Map<string, FilterOption>();

  for (const preparedPost of preparedPosts) {
    for (const region of preparedPost.matchedRegions) {
      if (options.has(region.id)) continue;
      options.set(region.id, {
        id: region.id,
        label: region.label,
        searchText: `${region.englishName} ${region.arabicName}`.trim(),
      });
    }
  }

  return Array.from(options.values()).sort((left, right) => left.label.localeCompare(right.label));
}

export function filterOfficialFeedPosts(
  preparedPosts: PreparedOfficialFeedPost[],
  filters: OfficialFeedFilterState,
): PreparedOfficialFeedPost[] {
  const selectedSourceIds = new Set(filters.selectedSources);
  const selectedRegionIds = new Set(filters.selectedRegionIds);
  const keywordLatin = normalizeLatinText(filters.keyword);
  const keywordArabic = normalizeArabicText(filters.keyword);

  return preparedPosts.filter((preparedPost) => {
    // Filters combine with AND logic: once any active filter fails, the post
    // is excluded from the visible Official Feeds list.
    if (selectedSourceIds.size > 0 && !selectedSourceIds.has(preparedPost.sourceId)) {
      return false;
    }

    if (selectedRegionIds.size > 0 && !preparedPost.matchedRegionIds.some((regionId) => selectedRegionIds.has(regionId))) {
      return false;
    }

    if (keywordLatin && !preparedPost.searchTextLatin.includes(keywordLatin)) {
      if (!keywordArabic || !preparedPost.searchTextArabic.includes(keywordArabic)) {
        return false;
      }
    }

    return true;
  });
}

export function groupOfficialFeedPostsByPublisher(preparedPosts: PreparedOfficialFeedPost[]): Record<string, PreparedOfficialFeedPost[]> {
  return preparedPosts.reduce<Record<string, PreparedOfficialFeedPost[]>>((groups, preparedPost) => {
    const key = preparedPost.post.publisherName;
    groups[key] = groups[key] ? [...groups[key], preparedPost] : [preparedPost];
    return groups;
  }, {});
}
