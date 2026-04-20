// Village-level sectarian distribution for Lebanon
// Colors inspired by standard Lebanese demographic reference maps

export type Sect =
  | 'maronite'
  | 'greek_orthodox'
  | 'greek_catholic'
  | 'armenian'
  | 'other_christian'
  | 'shia'
  | 'sunni'
  | 'alawite'
  | 'druze'
  | 'mixed';

export const SECT_COLORS: Record<Sect, string> = {
  maronite:        '#A84040',
  greek_orthodox:  '#B87248',
  greek_catholic:  '#A89040',
  armenian:        '#8A7A6E',
  other_christian: '#4A9090',
  shia:            '#2A6E2A',
  sunni:           '#3A5A9A',
  alawite:         '#6A3A7A',
  druze:           '#A84488',
  mixed:           '#606870',
};

export const SECT_LABELS: Record<Sect, string> = {
  maronite:        'Maronite Catholic',
  greek_orthodox:  'Greek Orthodox',
  greek_catholic:  'Greek Catholic (Melkite)',
  armenian:        'Armenian',
  other_christian: 'Other Christian',
  shia:            'Shia Muslim',
  sunni:           'Sunni Muslim',
  alawite:         'Alawite',
  druze:           'Druze',
  mixed:           'Mixed',
};

// Normalized GeoJSON NAME_2 → default sect for all villages in that district
// Keys must exactly match: name.trim().toLowerCase().replace(/-/g,' ').replace(/\s+/g,' ').normalize('NFD').replace(/[\u0300-\u036f]/g,'')
export const DISTRICT_DEFAULT_SECT: Record<string, Sect> = {
  'akkar':         'sunni',
  'minieh danieh': 'sunni',
  'baalbeck':      'shia',
  'hermel':        'shia',
  'beirut':        'sunni',
  'rachiaya':      'greek_orthodox',
  'westbekaa':     'greek_orthodox',
  'zahleh':        'greek_catholic',
  'aley':          'druze',
  'baabda':        'maronite',
  'batroun':       'maronite',
  'chouf':         'druze',
  'elmetn':        'maronite',
  'jezzine':       'greek_catholic',
  'jubail':        'maronite',
  'kasrouane':     'maronite',
  'bintjbayl':     'shia',
  'hasbaya':       'druze',
  'marjaayoun':    'greek_catholic',
  'nabatiyeh':     'shia',
  'bcharre':       'maronite',
  'koura':         'greek_orthodox',
  'tripoli':       'sunni',
  'zgharta':       'maronite',
  'saida':         'sunni',
  'sour':          'shia',
};

// Normalized GeoJSON NAME_3 → village-level sect override
// Overrides the district default for known villages with different sect composition
export const VILLAGE_SECT: Record<string, Sect> = {

  // ── BEIRUT (13 quarters) ──────────────────────────────────────────────────
  'achrafieh':             'maronite',      // East Beirut, historic Christian quarter
  'ainel mreisse':         'sunni',
  'bachoura':              'sunni',
  'beirutcentraldistrict': 'sunni',
  'mazraa':                'sunni',
  'medawar':               'armenian',      // Bourj Hammoud adjacent, Armenian community
  'minetel hosn':          'sunni',
  'moussaytbeh':           'sunni',
  'rasbeyrouth':           'sunni',
  'remeil':                'greek_orthodox', // Rmeil / Mar Mikhael area
  'saife':                 'maronite',      // Saifi / Gemmayzeh
  'zoukakel blatt':        'sunni',
  'port':                  'mixed',

  // ── BAABDA – Dahiyeh suburbs are Shia ─────────────────────────────────────
  'baabda':                'maronite',
  'hadace':                'maronite',      // Hadath
  'hazmiyeh':              'maronite',
  'bzebdine':              'maronite',
  'hammana':               'maronite',
  'falougha':              'maronite',
  'kernayel':              'maronite',
  'baalchemay':            'maronite',
  'bmariam':               'maronite',
  'louaize':               'maronite',
  'kfarchima':             'maronite',
  'kartada':               'maronite',
  'araya':                 'maronite',
  'fornel chobbek':        'maronite',      // Furn el-Chebbak
  'harethoraik':           'shia',          // Haret Hreik – Hezbollah political HQ
  'harethamze':            'shia',
  'borgeelbaragenat':      'shia',          // Bourj el-Barajneh
  'ghbayreh':              'shia',
  'chiah':                 'mixed',         // Shia/Maronite boundary neighbourhood
  'tahouitat el ghadir':   'shia',

  // ── ALEY – mostly Druze, Christian pockets in highland resorts ────────────
  'ainsofar':              'other_christian', // Ain Sofar – Christian summer resort
  'bhamdoun(village)':     'other_christian', // Bhamdoun Village was Christian
  'bhamdoun(gare)':        'sunni',

  // ── CHOUF – Druze heartland, two historic Maronite towns ──────────────────
  'deirel kamar':          'maronite',      // Deir el-Qamar – oldest Maronite town in Chouf
  'damour':                'greek_orthodox', // Damour – historic Greek Orthodox town
  'beiteddine':            'druze',
  'el moukhtara':          'druze',         // Mukhtara – Jumblatt family seat
  'baakline':              'druze',
  'daraya':                'druze',
  'niha':                  'druze',
  'el barouk':             'druze',
  'debbiyeh':              'druze',

  // ── ZAHLEH – Greek Catholic majority, two exceptions ─────────────────────
  'anjar':                 'armenian',      // Anjar – only Armenian town in Lebanon
  'talabaya':              'shia',          // Taalabaya – Shia village in Bekaa
  'bar elias':             'sunni',
  'chtaura':               'greek_catholic',
  'ablah':                 'greek_catholic',
  'ksara':                 'greek_catholic',
  'rayak':                 'greek_catholic',

  // ── BAALBECK – Shia majority; Deir el-Ahmar is a Maronite enclave ─────────
  'baalbeck':              'mixed',         // City: Shia majority + Sunni minority
  'dairel ahmar':          'maronite',      // Deir el-Ahmar – Maronite town in Bekaa
  'yamoune':               'maronite',      // Yammouneh – Maronite/mixed village
  'nahle':                 'sunni',         // Naaleh – Sunni village
  'arsale':                'sunni',         // Arsal – Sunni town near Syrian border

  // ── HERMEL – Ras Baalbek is a Christian (Greek Orthodox) village ──────────
  'ras baalbek wadifaara': 'greek_orthodox',
  'rasbaalbekkel gharbi':  'greek_orthodox',
  'rasbaalbekkel charki':  'greek_orthodox', // RasBaalbekEl-Charki
  'rasbaalbekkel sahl':    'greek_orthodox',  // RasBaalbekEl-Sahl

  // ── BINT JBEIL – two Greek Catholic Christian enclaves ───────────────────
  'ain ebel':              'greek_catholic', // Ain Ebel – Christian village in deep south
  'rmaich':                'greek_catholic', // Rmeich – Christian village

  // ── MARJAYOUN ─────────────────────────────────────────────────────────────
  'marjaayoun':            'greek_catholic',

  // ── HASBAYA – town itself is Greek Orthodox, surroundings are Druze ───────
  'hasbaya':               'greek_orthodox',

  // ── AKKAR – Alawite villages on coastal strip near Syrian border ──────────
  'bireh':                 'alawite',
  'dweir':                 'alawite',
  'qalhat':                'alawite',
  'beit mellat':           'alawite',
  'berqayl':               'alawite',
};
