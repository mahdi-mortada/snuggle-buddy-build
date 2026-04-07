type LooseRecord = Record<string, unknown>;

const SOURCE_LINK_KEYS = ['url', 'source_url', 'link', 'sourceUrl', 'postUrl', 'accountUrl'] as const;

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

export function resolveSourceUrl(value: unknown): string | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const record = value as LooseRecord;
  for (const key of SOURCE_LINK_KEYS) {
    const candidate = record[key];
    if (isNonEmptyString(candidate)) {
      return candidate.trim();
    }
  }

  return null;
}

export function openSourceUrl(url: string): void {
  window.open(url, '_blank', 'noopener,noreferrer');
}
