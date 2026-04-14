"""Hate Speech Detection Service.

Multi-lingual hate speech detection for Arabic, English, and French content.
Uses HuggingFace zero-shot classification as the primary detection method
(no fine-tuned model download required — works out of the box).

Detection categories:
  sectarian        → religious/sect targeting (Sunni/Shia/Christian/Druze)
  anti_refugee     → Syrian/Palestinian rhetoric
  political_incite → calls to violence against groups or persons
  misogynistic     → gender-based hate targeting women
  clean            → no hate speech detected
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from langdetect import detect as _langdetect
from langdetect import LangDetectException

logger = logging.getLogger(__name__)

# ── Hate speech label sets per language ──────────────────────────────────────

_ZERO_SHOT_LABELS_AR = [
    "خطاب كراهية طائفية",       # sectarian hate speech
    "تحريض ضد اللاجئين",        # incitement against refugees
    "تحريض على العنف السياسي",   # political violence incitement
    "خطاب كراهية ضد المرأة",     # misogynistic hate speech
    "محتوى مقبول",               # acceptable content
]

_ZERO_SHOT_LABELS_EN = [
    "sectarian hate speech",
    "anti-refugee incitement",
    "political violence incitement",
    "misogynistic hate speech",
    "acceptable content",
]

_ZERO_SHOT_LABELS_FR = [
    "discours de haine sectaire",
    "incitation contre les réfugiés",
    "incitation à la violence politique",
    "discours de haine misogyne",
    "contenu acceptable",
]

_LABEL_TO_CATEGORY = {
    # Arabic
    "خطاب كراهية طائفية": "sectarian",
    "تحريض ضد اللاجئين": "anti_refugee",
    "تحريض على العنف السياسي": "political_incite",
    "خطاب كراهية ضد المرأة": "misogynistic",
    "محتوى مقبول": "clean",
    # English
    "sectarian hate speech": "sectarian",
    "anti-refugee incitement": "anti_refugee",
    "political violence incitement": "political_incite",
    "misogynistic hate speech": "misogynistic",
    "acceptable content": "clean",
    # French
    "discours de haine sectaire": "sectarian",
    "incitation contre les réfugiés": "anti_refugee",
    "incitation à la violence politique": "political_incite",
    "discours de haine misogyne": "misogynistic",
    "contenu acceptable": "clean",
}

# ── Keyword boosters — fast pre-filter before model ──────────────────────────
# These increase the confidence score when matched.

_SECTARIAN_KEYWORDS = [
    # Arabic slurs / sectarian terms (transliterated + Arabic script)
    "شيعي", "سني", "ماروني", "درزي", "علوي", "كافر", "روافض", "نواصب",
    "حزب الشيطان", "ميليشيا",
    # English
    "shia", "sunni", "maronite", "druze", "kafir", "infidel", "militia",
]
_REFUGEE_KEYWORDS = [
    "نازح", "لاجئ", "سوري", "فلسطيني", "مخيم", "النازحين", "اللاجئين",
    "refugee", "displaced", "syrian", "palestinian", "camp",
    "réfugié", "déplacé", "syrien", "palestinien",
]
_INCITE_KEYWORDS = [
    "اقتلوا", "اذبحوا", "أعدموا", "يستحق الموت", "يجب تصفيته",
    "kill", "murder", "execute", "eliminate", "death to",
    "tuer", "éliminer", "mort à",
]
_MISOGYNY_KEYWORDS = [
    "عاهرة", "قحبة", "ناقصة عقل",
    "whore", "bitch", "go back to kitchen", "woman should",
    "putain", "salope",
]

_KEYWORD_SETS: dict[str, list[str]] = {
    "sectarian": _SECTARIAN_KEYWORDS,
    "anti_refugee": _REFUGEE_KEYWORDS,
    "political_incite": _INCITE_KEYWORDS,
    "misogynistic": _MISOGYNY_KEYWORDS,
}


@dataclass
class HateSpeechResult:
    text: str
    language: str                        # 'ar', 'en', 'fr', 'mix', 'unknown'
    hate_score: float                    # 0–100
    category: str                        # sectarian / anti_refugee / political_incite / misogynistic / clean
    is_flagged: bool                     # hate_score >= 51
    keyword_matches: list[str] = field(default_factory=list)
    model_confidence: float = 0.0        # raw model output 0–1
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class HateSpeechDetector:
    """Multilingual hate speech detector using zero-shot classification."""

    def __init__(self) -> None:
        self._classifier: object | None = None
        self._classifier_loaded = False

    def _load_classifier(self) -> None:
        if self._classifier_loaded:
            return
        try:
            from transformers import pipeline  # type: ignore[import]
            self._classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=-1,  # CPU
            )
            logger.info("Zero-shot hate speech classifier loaded")
        except Exception as exc:
            logger.warning("Could not load zero-shot classifier: %s — keyword-only mode", exc)
            self._classifier = None
        self._classifier_loaded = True

    def _detect_language(self, text: str) -> str:
        """Detect language: returns 'ar', 'en', 'fr', or 'mix'/'unknown'."""
        clean = re.sub(r"http\S+|@\w+|#\w+|\s+", " ", text).strip()
        if not clean:
            return "unknown"

        ar_chars = len(re.findall(r"[\u0600-\u06FF]", clean))
        total = len(clean.replace(" ", ""))
        if total == 0:
            return "unknown"

        ar_ratio = ar_chars / total
        if ar_ratio > 0.5:
            return "ar"

        try:
            lang = _langdetect(clean)
            if lang in ("ar", "en", "fr"):
                return lang
            return "en"  # default latin to English
        except LangDetectException:
            return "unknown"

    def _keyword_scan(self, text: str) -> dict[str, list[str]]:
        """Scan text for hate speech keywords. Returns {category: [matches]}."""
        lower = text.lower()
        found: dict[str, list[str]] = {}
        for category, keywords in _KEYWORD_SETS.items():
            matches = [kw for kw in keywords if kw in lower]
            if matches:
                found[category] = matches
        return found

    def _labels_for_language(self, lang: str) -> list[str]:
        if lang == "ar":
            return _ZERO_SHOT_LABELS_AR
        if lang == "fr":
            return _ZERO_SHOT_LABELS_FR
        return _ZERO_SHOT_LABELS_EN

    async def analyze(self, text: str) -> HateSpeechResult:
        """Analyze a single text for hate speech. Returns a HateSpeechResult."""
        if not text or not text.strip():
            return HateSpeechResult(
                text=text, language="unknown", hate_score=0.0,
                category="clean", is_flagged=False,
            )

        lang = self._detect_language(text)
        keyword_hits = self._keyword_scan(text)

        # ── Keyword-only fast path ─────────────────────────────────────────────
        keyword_score = 0.0
        keyword_category = "clean"
        all_matches: list[str] = []

        for cat, matches in keyword_hits.items():
            all_matches.extend(matches)
            # Weight: incitement > sectarian > refugee > misogyny
            weight = {
                "political_incite": 35.0,
                "sectarian": 28.0,
                "anti_refugee": 22.0,
                "misogynistic": 20.0,
            }.get(cat, 15.0)
            score = min(70.0, weight * len(matches))
            if score > keyword_score:
                keyword_score = score
                keyword_category = cat

        # ── Model path (if available) ─────────────────────────────────────────
        model_score = 0.0
        model_category = "clean"
        model_confidence = 0.0

        self._load_classifier()
        if self._classifier is not None:
            try:
                labels = self._labels_for_language(lang)
                # Truncate to 512 chars for the model
                result = self._classifier(text[:512], labels, multi_label=False)  # type: ignore[call-arg]
                top_label: str = result["labels"][0]
                top_score: float = float(result["scores"][0])
                model_confidence = top_score
                model_category = _LABEL_TO_CATEGORY.get(top_label, "clean")

                if model_category != "clean":
                    model_score = top_score * 100.0
            except Exception as exc:
                logger.debug("Classifier error: %s", exc)

        # ── Merge scores ──────────────────────────────────────────────────────
        # Take the higher of keyword or model score, then cap at 100
        hate_score = max(keyword_score, model_score)

        # Agreement bonus: if both signals agree on same non-clean category
        if keyword_category != "clean" and keyword_category == model_category:
            hate_score = min(100.0, hate_score * 1.15)

        category = model_category if model_score >= keyword_score else keyword_category
        if hate_score < 5.0:
            category = "clean"

        return HateSpeechResult(
            text=text,
            language=lang,
            hate_score=round(hate_score, 1),
            category=category,
            is_flagged=hate_score >= 51.0,
            keyword_matches=all_matches,
            model_confidence=round(model_confidence, 3),
        )


hate_speech_detector = HateSpeechDetector()
