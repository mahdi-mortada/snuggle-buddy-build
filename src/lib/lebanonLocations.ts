type LocationScript = 'arabic' | 'latin';

type LocationAlias = {
  normalized: string;
  tokens: string[];
  script: LocationScript;
};

export type RegionOption = {
  id: string;
  label: string;
  englishName: string;
  arabicName: string;
  searchText: string;
};

type RegionEntry = RegionOption & {
  aliases: LocationAlias[];
};

type OSMRawElement = {
  tags?: Record<string, unknown>;
};

type OSMRawFeature = {
  properties?: Record<string, unknown>;
};

export type OSMRawData = {
  elements?: OSMRawElement[];
  features?: OSMRawFeature[];
};

export type LebanonLocationIndex = {
  regions: RegionOption[];
  regionLookup: Map<string, RegionEntry>;
  arabicTokenIndex: Map<string, Set<string>>;
  latinTokenIndex: Map<string, Set<string>>;
};

const ARABIC_CHARS = /[\u0600-\u06FF]/;

export function buildLebanonLocationIndex(raw: OSMRawData): LebanonLocationIndex {
  const registry = new Map<string, RegionEntry>();

  const registerProperties = (properties?: Record<string, unknown>) => {
    if (!properties) return;

    // Build a bilingual alias list from GeoJSON properties so a single region
    // option can be matched whether the feed or the user input is Arabic or English.
    const aliases = collectAliases(properties);
    if (aliases.length === 0) return;

    const englishName = readPrimaryName(properties, ['name:en', 'name', 'alt_name']);
    const arabicName = readPrimaryName(properties, ['name:ar', 'alt_name:ar', 'name:arz']);

    const fallbackAlias = aliases[0];
    const displayEnglish = englishName || (fallbackAlias.script === 'latin' ? fallbackAlias.raw : '');
    const displayArabic = arabicName || (fallbackAlias.script === 'arabic' ? fallbackAlias.raw : '');

    const regionId = normalizeLatinText(displayEnglish) || normalizeArabicText(displayArabic) || fallbackAlias.normalized;
    if (!regionId) return;

    const current = registry.get(regionId);
    if (!current) {
      registry.set(regionId, {
        id: regionId,
        label: buildRegionLabel(displayEnglish, displayArabic),
        englishName: displayEnglish || displayArabic || fallbackAlias.raw,
        arabicName: displayArabic,
        searchText: aliases.map((alias) => alias.raw).join(' '),
        aliases: aliases.map(({ normalized, tokens, script }) => ({ normalized, tokens, script })),
      });
      return;
    }

    const seenAliases = new Set(current.aliases.map((alias) => `${alias.script}:${alias.normalized}`));
    for (const alias of aliases) {
      const aliasKey = `${alias.script}:${alias.normalized}`;
      if (seenAliases.has(aliasKey)) continue;
      current.aliases.push({
        normalized: alias.normalized,
        tokens: alias.tokens,
        script: alias.script,
      });
      seenAliases.add(aliasKey);
      current.searchText = `${current.searchText} ${alias.raw}`.trim();
    }

    if (!current.englishName && displayEnglish) {
      current.englishName = displayEnglish;
    }
    if (!current.arabicName && displayArabic) {
      current.arabicName = displayArabic;
    }
    current.label = buildRegionLabel(current.englishName, current.arabicName);
  };

  if (Array.isArray(raw.elements)) {
    for (const element of raw.elements) {
      registerProperties(element.tags);
    }
  }

  if (Array.isArray(raw.features)) {
    for (const feature of raw.features) {
      registerProperties(feature.properties);
    }
  }

  const regions = Array.from(registry.values())
    .sort((left, right) => left.label.localeCompare(right.label))
    .map(({ aliases: _aliases, ...region }) => region);

  const arabicTokenIndex = new Map<string, Set<string>>();
  const latinTokenIndex = new Map<string, Set<string>>();

  for (const entry of registry.values()) {
    for (const alias of entry.aliases) {
      // Index aliases by token to avoid scanning the full Lebanon location list
      // for every post during dynamic filtering.
      const targetIndex = alias.script === 'arabic' ? arabicTokenIndex : latinTokenIndex;
      for (const token of alias.tokens) {
        if (!targetIndex.has(token)) {
          targetIndex.set(token, new Set());
        }
        targetIndex.get(token)?.add(entry.id);
      }
    }
  }

  return {
    regions,
    regionLookup: registry,
    arabicTokenIndex,
    latinTokenIndex,
  };
}

export function inferRegionIdsFromText(text: string, index: LebanonLocationIndex | null): string[] {
  if (!index || !text.trim()) return [];

  // We gather cheap token candidates first, then verify phrase-level matches
  // so the location filter stays responsive even with larger GeoJSON datasets.
  const arabicTokens = tokenizeArabicWords(text);
  const latinTokens = tokenizeLatinWords(text);
  const candidateIds = new Set<string>();

  for (const token of arabicTokens) {
    for (const regionId of index.arabicTokenIndex.get(token) ?? []) {
      candidateIds.add(regionId);
    }
  }

  for (const token of latinTokens) {
    for (const regionId of index.latinTokenIndex.get(token) ?? []) {
      candidateIds.add(regionId);
    }
  }

  const matchedIds: string[] = [];
  for (const regionId of candidateIds) {
    const region = index.regionLookup.get(regionId);
    if (!region) continue;

    const hasMatch = region.aliases.some((alias) => {
      const haystackTokens = alias.script === 'arabic' ? arabicTokens : latinTokens;
      return hasExactTokenMatch(haystackTokens, alias.tokens);
    });

    if (hasMatch) {
      matchedIds.push(regionId);
    }
  }

  return matchedIds.sort((left, right) => {
    const leftRegion = index.regionLookup.get(left);
    const rightRegion = index.regionLookup.get(right);
    return (leftRegion?.label ?? left).localeCompare(rightRegion?.label ?? right);
  });
}

export function normalizeArabicText(value: string | undefined): string {
  if (!value) return '';

  return value
    .normalize('NFKD')
    .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g, '')
    .replace(/[\u0640]/g, '')
    .replace(/[أإآٱ]/g, 'ا')
    .replace(/[ؤ]/g, 'و')
    .replace(/[ئ]/g, 'ي')
    .replace(/[ى]/g, 'ي')
    .replace(/[ة]/g, 'ه')
    .replace(/[^\u0621-\u064A0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .map((token) => token.replace(/^\u0627\u0644/u, ''))
    .filter(Boolean)
    .join(' ');
}

export function normalizeLatinText(value: string | undefined): string {
  if (!value) return '';

  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function collectAliases(properties: Record<string, unknown>): Array<{ raw: string; normalized: string; tokens: string[]; script: LocationScript }> {
  const aliasKeys = ['name:ar', 'name:en', 'name', 'name:arz', 'alt_name', 'alt_name:ar', 'official_name', 'old_name'];
  const aliases: Array<{ raw: string; normalized: string; tokens: string[]; script: LocationScript }> = [];
  const seen = new Set<string>();

  for (const key of aliasKeys) {
    const rawValue = properties[key];
    if (typeof rawValue !== 'string') continue;

    const parts = rawValue
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean);

    for (const raw of parts) {
      const script: LocationScript = ARABIC_CHARS.test(raw) ? 'arabic' : 'latin';
      const tokens = script === 'arabic' ? tokenizeArabicWords(raw) : tokenizeLatinWords(raw);
      if (tokens.length === 0) continue;

      const normalized = tokens.join(' ');
      const aliasKey = `${script}:${normalized}`;
      if (seen.has(aliasKey)) continue;
      seen.add(aliasKey);
      aliases.push({ raw, normalized, tokens, script });
    }
  }

  return aliases;
}

function tokenizeArabicWords(text: string | undefined): string[] {
  if (!text) return [];
  return normalizeArabicText(text)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function tokenizeLatinWords(text: string | undefined): string[] {
  if (!text) return [];
  return normalizeLatinText(text)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function hasExactTokenMatch(haystackTokens: string[], needleTokens: string[]): boolean {
  if (haystackTokens.length === 0 || needleTokens.length === 0) {
    return false;
  }

  if (needleTokens.length === 1) {
    return haystackTokens.includes(needleTokens[0]);
  }

  for (let index = 0; index <= haystackTokens.length - needleTokens.length; index += 1) {
    let isMatch = true;
    for (let offset = 0; offset < needleTokens.length; offset += 1) {
      if (haystackTokens[index + offset] !== needleTokens[offset]) {
        isMatch = false;
        break;
      }
    }
    if (isMatch) return true;
  }

  return false;
}

function buildRegionLabel(englishName: string, arabicName: string): string {
  if (englishName && arabicName) {
    return `${englishName} / ${arabicName}`;
  }
  return englishName || arabicName;
}

function readPrimaryName(properties: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = properties[key];
    if (typeof value === 'string' && value.trim()) {
      return value
        .split(';')
        .map((part) => part.trim())
        .find(Boolean) ?? '';
    }
  }
  return '';
}
