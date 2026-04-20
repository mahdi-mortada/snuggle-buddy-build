import { LEBANON_DISTRICTS } from './lebanon_districts_metadata';

export function normalize(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/-/g, ' ')
    .replace(/\s+/g, ' ')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

// Maps known GeoJSON NAME_2 variants (post-normalization) to canonical metadata name_en (post-normalization)
export const ALIASES: Record<string, string> = {
  'baalbeck':        'baalbek',
  'bintjbayl':       'bint jbeil',   // GeoJSON: "BintJbayl" (no space)
  'elmetn':          'metn',          // GeoJSON: "ElMetn" (no space)
  'jubail':          'jbeil',
  'kasrouane':       'keserwan',
  'marjaayoun':      'marjayoun',
  'minieh danieh':   'minieh danniyeh',
  'nabatiyeh':       'nabatieh',
  'rachiaya':        'rashaya',
  'westbekaa':       'west bekaa',    // GeoJSON: "WestBekaa" (no space)
  'zahleh':          'zahle',         // GeoJSON: "Zahleh" vs metadata "Zahle"
  'sidon':           'saida',
  'tyre':            'sour',
  'akkar district':  'akkar',
  'beirut district': 'beirut',
};

export const districtColorMap = new Map<string, string>(
  LEBANON_DISTRICTS.map((d) => [normalize(d.name_en), d.color]),
);

export function getDistrictColor(name2: string): string | null {
  const key = normalize(name2);
  const resolved = ALIASES[key] ?? key;
  return districtColorMap.get(resolved) ?? null;
}
