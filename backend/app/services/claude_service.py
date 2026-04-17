"""Claude AI unified analysis service for Official Feeds post enrichment.

Each post is analyzed in a single API call that returns:
  - scenario_type : best-fit incident category
  - signals       : short threat/event strings detected in the text
  - severity      : low / medium / high / critical
  - sentiment     : calm / tension / panic / escalation
  - locations     : geographic place names EXPLICITLY present in the text
  - confidence_score : 0.0-1.0 float
  - is_rumor      : whether the post appears unverified

Results are cached in-memory keyed by a 16-char SHA-256 prefix so the same
post is never sent to Claude twice within the process lifetime.

The single unified call replaces the former two-call pattern
(analyze_text + resolve_location_with_ai) to halve API latency per post.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

# ─── Fallback returned on any error ──────────────────────────────────────────

_FALLBACK: dict[str, object] = {
    "scenario_type": "unclear",
    "signals": [],
    "severity": "low",
    "sentiment": "calm",
    "locations": [],
    "confidence_score": 0.0,
    "location_confidence": 0.0,
    "is_rumor": False,
    "_status": "error",  # overridden per-call below
}

# In-memory cache: sha256_prefix -> full analysis dict
_cache: dict[str, dict[str, object]] = {}

_TIMEOUT = 15.0  # seconds — single call budget (was 12 + 8 separately)

# ─── Unified system prompt ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an AI intelligence agent integrated into a real-time Lebanese conflict monitoring system.

Your role is to analyze raw news content (Arabic, English, or mixed) and return ONLY a valid JSON object.
No markdown, no explanation, no extra text — just the raw JSON.

Required structure:
{
  "scenario_type": "one of: armed_conflict, protest, natural_disaster, infrastructure_failure, health_emergency, terrorism, cyber_attack, political_tension, civilian_displacement, other",
  "signals": ["signal1", "signal2"],
  "severity": "one of: low, medium, high, critical",
  "sentiment": "one of: calm, tension, panic, escalation",
  "locations": ["exact substring copied from input"],
  "confidence_score": 0.85,
  "location_confidence": 0.9,
  "is_rumor": false
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- scenario_type: pick the single best match from the allowed values
- signals: 1-5 short English strings describing detected threats, events, or actors
- severity: low=routine info, medium=notable, high=serious threat, critical=immediate danger to life
- sentiment: calm=no urgency/routine, tension=elevated concern, panic=immediate fear or chaos, escalation=situation actively worsening
- confidence_score: 0.0-1.0 reflecting your certainty about the full analysis
- location_confidence: 0.0-1.0 reflecting ONLY your confidence that every string in "locations" is a real Lebanese place (town/city/area) where an event is actually taking place. Use 0.9+ only when the locative context is unambiguous. Use 0.0 when no locations were extracted.
- is_rumor: true when the post uses phrases like "reportedly", "sources say", or is clearly speculative

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOCATION EXTRACTION — MANDATORY PROCESS (FOLLOW IN ORDER)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. READ the full text carefully
2. UNDERSTAND the context — what event is happening and WHERE
3. IDENTIFY candidate location words or phrases
4. VALIDATE each candidate using the strict rules below
5. RETURN only the final verified locations

STRICT VALIDATION RULES:

1. CONTEXT FIRST — do NOT extract words blindly.
   Only extract locations where an event is actually taking place.
   You MUST understand what the sentence is describing before extracting anything.

2. REAL LEBANESE LOCATIONS ONLY — the extracted location must be:
   - A real town, village, city, or well-known area in Lebanon
   - Explicitly mentioned in the text as a PLACE (not coincidentally spelled like one)
   - If uncertain → DO NOT include it

3. EXACT MATCH — a location MUST be an exact substring of the input text.
   Copy character-for-character. If it does not appear exactly → DO NOT include it.

4. LOCATIVE CONTEXT REQUIRED (KEY RULE):
   Any word that also exists as a common Arabic word must appear with at least ONE
   locative signal to be accepted as a genuine place reference:

   a) Location prepositions near the word:
      في (in), إلى (to), من (from), نحو (toward), قرب / بالقرب من (near),
      على (at), فوق (above), داخل (inside), خارج (outside)

   b) Location-event verbs near the word:
      استهدف (targeted), قصف (bombed/shelled), اقتحم (stormed),
      تقدم نحو (advanced toward), دخل (entered), غادر (left),
      انسحب من (withdrew from), وصل إلى (reached), سقط في (fell in)

   c) Explicit place nouns before it:
      بلدة (town of), مدينة (city of), قرية (village of), منطقة (area of),
      محلة (neighborhood of), حي (district of), ضاحية (suburb of)

   If NONE of these signals are present → treat it as a common word, NOT a location.

5. COMPOSED NAMES (CRITICAL) — many Lebanese locations are multi-word:
   - Treat the FULL name as one entity
   - DO NOT split, DO NOT extract partial matches, DO NOT confuse similar names
   Examples:
     "بنت جبيل" ≠ "جبيل"  →  extract "بنت جبيل" only
     "عين التينة" ≠ "عين" →  extract "عين التينة" only
     "بيت مري" ≠ "مري"    →  extract "بيت مري" only

6. KNOWN AMBIGUOUS WORDS — these words are both common Arabic words AND Lebanese place names.
   Apply the locative context rule (rule 4) strictly to each:

   صور   → also means "photos/images"
           WRONG: "نشر الجيش صور الاشتباك" (= published photos of the clash)
           CORRECT: "غارة على مدينة صور" (= airstrike on the city of Tyre)

   الوقف → also means "endowment/foundation"
           WRONG: "قرار بشأن الوقف الديني" (= decision about religious endowment)
           CORRECT: "اشتباك في منطقة الوقف" (= clash in the Waqf area)

   الواقف / واقف → also means "standing/stopped"
           WRONG: "الشخص الواقف أمام المبنى" (= the person standing in front)
           CORRECT: "قوات عند الواقف" (= forces at Al-Waqef)

   مرجعيون → also used as plural of "مرجعية" (religious/political authority)
           WRONG: "المرجعيون الدينية أصدرت بياناً" (= religious authorities issued statement)
           CORRECT: "قصف طال مرجعيون" (= shelling hit Marjayoun)

   سور   → also means "wall/fence"
           WRONG: "انهار سور المبنى" (= the building wall collapsed)
           CORRECT: "دخول إلى سور الصور" (= entering the wall area of Sour)

   طيبة  → also means "good/kind"
           WRONG: "نتائج طيبة للمفاوضات" (= good results for negotiations)
           CORRECT: "دخول قوات إلى طيبة" (= forces entering Taybeh)

7. RECOGNIZED INFORMAL AREAS — these are NOT official administrative units but are
   well-known geographic references in Lebanese news and MUST be extracted when used
   as location references:

   الضاحية / الضاحية الجنوبية → the southern suburb of Beirut (Dahiyeh), a major
           Beirut area. Extract when used as a place reference.
           CORRECT: "غارة استهدفت الضاحية الجنوبية" → ["الضاحية الجنوبية"]
           CORRECT: "في الضاحية" → ["الضاحية"]
           Note: "الضاحية" alone without adjective is sufficient — extract it.

8. FALSE POSITIVES — DO NOT extract:
   - Adjectives: "جديدة" (new), "كبيرة" (big), "جنوبية" alone as an adjective, "قديمة" (old)
   - Directions used generically: "الجنوب" (the south), "الشمال" (the north) when used as
     compass directions or general regions, NOT as specific named places
   - Person names, organization names
   - Generic words: road, area, highway, street

9. MULTIPLE LOCATIONS — return ALL valid ones found; if only one → return only that one.
   DO NOT infer, add nearby, or expand to similar locations.

10. NO HALLUCINATION — NEVER add locations not in the text.
    NEVER expand: "عين التينة" ≠ "عين الدلب". NEVER guess.

11. BACKEND VALIDATION — output is validated programmatically.
    Any location not found as an exact substring will be removed.
    No duplicates, no extra spaces.

If NO valid Lebanese location is clearly mentioned → return "locations": []

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOCATION EXAMPLES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Input: "غارة جديدة استهدفت بلدة كفررمان"
→ locations: ["كفررمان"]   (بلدة = locative signal ✓)

Input: "نشر الجيش صور الاشتباك على وسائل التواصل"
→ locations: []   (صور = photos, no locative signal around it)

Input: "غارة استهدفت مدينة صور جنوب لبنان"
→ locations: ["صور"]   (مدينة = locative signal ✓)

Input: "عين التينة تشهد تحركات سياسية"
→ locations: ["عين التينة"]   (subject of event verb ✓)

Input: "قرار بشأن الوقف الديني في بيروت"
→ locations: ["بيروت"]   (الوقف = endowment here; بيروت has في ✓)

Input: "قوات الاحتلال تتقدم نحو مرجعيون"
→ locations: ["مرجعيون"]   (تتقدم نحو = movement toward ✓)

Input: "غارة استهدفت الضاحية الجنوبية لبيروت"
→ locations: ["الضاحية الجنوبية"]   (informal area, recognized ✓)

Input: "تقرير من الضاحية عن أضرار جسيمة"
→ locations: ["الضاحية"]   (informal area, recognized ✓)

Input: "غارة جديدة على الطريق الدولي"
→ locations: []   (no specific Lebanese place)

Output ONLY the JSON object, nothing else."""


# ─── Public API ───────────────────────────────────────────────────────────────

async def analyze_post(text: str) -> dict[str, object]:
    """Single unified Claude call: returns scenario, signals, severity, sentiment,
    locations, confidence, and is_rumor.

    Returns cached result on repeat calls.
    Falls back to _FALLBACK on timeout, parse error, or API failure. Never raises.
    """
    cache_key = hashlib.sha256(text.encode()).hexdigest()[:16]
    if cache_key in _cache:
        logger.debug("Claude cache hit: key=%s", cache_key)
        return _cache[cache_key]

    from app.config import get_settings  # lazy import avoids circular deps at module load
    settings = get_settings()

    if not settings.claude_api_key:
        logger.debug("CLAUDE_API_KEY not configured — skipping AI analysis")
        return {**_FALLBACK, "_status": "missing_key"}

    logger.info("Claude unified analysis starting (text_len=%d, key=%s)", len(text), cache_key)
    try:
        result = await asyncio.wait_for(
            _call_claude(text, settings.claude_api_key),
            timeout=_TIMEOUT,
        )
        result["_status"] = "success"
        _cache[cache_key] = result
        logger.info(
            "Claude analysis succeeded: scenario=%s severity=%s sentiment=%s locations=%r (cache_size=%d)",
            result.get("scenario_type"),
            result.get("severity"),
            result.get("sentiment"),
            result.get("locations"),
            len(_cache),
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Claude analysis timed out after %.1fs", _TIMEOUT)
        return {**_FALLBACK, "_status": "timeout"}
    except Exception as exc:
        logger.warning("Claude analysis failed: %s", exc)

    return {**_FALLBACK, "_status": "error"}


# ─── Compatibility wrappers (thin delegates to analyze_post) ─────────────────

async def analyze_text(text: str) -> dict[str, object]:
    """Backward-compatible wrapper — returns the analysis subset without locations.

    Callers that only need signals/scenario/severity/confidence/is_rumor can keep
    using this function; it now reuses the unified cache so no extra API call is made.
    """
    result = await analyze_post(text)
    return {
        "signals": result.get("signals", []),
        "scenario_type": result.get("scenario_type", "unclear"),
        "severity": result.get("severity", "low"),
        "confidence_score": result.get("confidence_score", 0.0),
        "is_rumor": result.get("is_rumor", False),
    }


async def resolve_location_with_ai(text: str) -> dict[str, object]:
    """Backward-compatible wrapper — returns only the location subset.

    Reuses the unified cache so no extra API call is made.
    """
    result = await analyze_post(text)
    locations = result.get("locations", [])
    confidence = result.get("confidence_score", 0.0) if locations else 0.0
    return {
        "locations": locations,
        "confidence": confidence,
    }


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """Extract the first JSON object from a string.

    Slices from the first '{' to the last '}' so code fences, leading text,
    and any trailing explanation from the model are all ignored.
    """
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in response: {raw!r}")
    return json.loads(raw[start : end + 1])


async def _call_claude(text: str, api_key: str) -> dict[str, object]:
    """Make the Anthropic API call and parse + validate the unified JSON response."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,  # enough for all 7 fields with richer location output
        temperature=0.0,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text[:1500]}],
    )

    parsed: dict = _extract_json(response.content[0].text)

    # Hard validation for locations: only keep strings that are literal substrings
    # of the original text — enforcement layer that catches model hallucinations.
    raw_locations = parsed.get("locations", []) or []
    validated_locations = [
        str(loc).strip()
        for loc in raw_locations
        if loc and str(loc).strip() and str(loc).strip() in text
    ]

    # Validate sentiment against allowed values
    allowed_sentiments = {"calm", "tension", "panic", "escalation"}
    raw_sentiment = str(parsed.get("sentiment", "calm")).strip().lower()
    sentiment = raw_sentiment if raw_sentiment in allowed_sentiments else "calm"

    raw_loc_conf = parsed.get("location_confidence")
    if raw_loc_conf is None:
        # Fallback: derive from overall confidence, but cap at 0.85 so it stays
        # below the display threshold unless Claude explicitly reported high certainty.
        location_confidence = min(float(parsed.get("confidence_score", 0.0)), 0.85)
    else:
        location_confidence = float(raw_loc_conf)
    # No locations → zero confidence regardless of what the model returned.
    if not validated_locations:
        location_confidence = 0.0

    return {
        "scenario_type": str(parsed.get("scenario_type", "other")).strip(),
        "signals": [str(s) for s in parsed.get("signals", [])][:5],
        "severity": str(parsed.get("severity", "low")).strip(),
        "sentiment": sentiment,
        "locations": validated_locations,
        "confidence_score": float(parsed.get("confidence_score", 0.0)),
        "location_confidence": round(location_confidence, 3),
        "is_rumor": bool(parsed.get("is_rumor", False)),
    }
