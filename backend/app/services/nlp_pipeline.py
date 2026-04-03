"""NLP Processing Pipeline — Section 4.

Steps (in order):
  1. Language detection (langdetect)
  2. Text cleaning + Arabic normalization
  3. Named Entity Recognition (spaCy)
  4. Sentiment analysis (HuggingFace)
  5. Topic classification (zero-shot BART)
  6. Threat keyword scoring (Redis weights)

All heavy models are loaded ONCE at startup via NLPPipeline.initialize().
Individual steps fail gracefully so a partial result is always returned.
"""
from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Arabic normalization helpers ─────────────────────────────────────────────

_ALEF_RE = re.compile(r"[أإآ]")
_YA_RE = re.compile(r"ى")
_TA_RE = re.compile(r"ة")
_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_MENTION_RE = re.compile(r"@\w+")
_HASHTAG_RE = re.compile(r"#(\w+)")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


def _clean_text(text: str) -> str:
    """Remove URLs, mentions; keep hashtag text; normalize whitespace."""
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(r"\1", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def _normalize_arabic(text: str) -> str:
    """Normalize Arabic script: remove diacritics, unify alef/ya/ta."""
    text = _DIACRITICS_RE.sub("", text)
    text = _ALEF_RE.sub("ا", text)
    text = _YA_RE.sub("ي", text)
    text = _TA_RE.sub("ه", text)
    return text


# ── Incident category labels ─────────────────────────────────────────────────

CATEGORY_LABELS = [
    "violence",
    "protest",
    "natural disaster",
    "infrastructure failure",
    "health emergency",
    "terrorism",
    "cyber attack",
    "armed conflict",
    "other",
]

CATEGORY_MAP = {
    "violence": "violence",
    "protest": "protest",
    "natural disaster": "natural_disaster",
    "infrastructure failure": "infrastructure",
    "health emergency": "health",
    "terrorism": "terrorism",
    "cyber attack": "cyber",
    "armed conflict": "armed_conflict",
    "other": "other",
}


class NLPPipeline:
    """Full NLP pipeline. Call initialize() once at application startup."""

    def __init__(self) -> None:
        self._initialized = False
        # spaCy models
        self._nlp_en = None
        self._nlp_xx = None
        # HuggingFace pipelines
        self._sentiment_en = None
        self._sentiment_ar = None
        self._classifier = None
        # Redis threat keywords (loaded on demand)
        self._keywords: dict[str, float] = {}

        # Legacy keyword dict for fallback when HuggingFace is unavailable
        self.category_keywords: dict[str, list[str]] = {
            "violence": ["shooting", "attack", "roadblock", "clash", "gunfire", "gun"],
            "protest": ["protest", "crowd", "march", "demonstration", "rally"],
            "natural_disaster": ["earthquake", "flood", "fire", "storm", "disaster"],
            "infrastructure": ["blackout", "outage", "collapse", "explosion", "bridge"],
            "health": ["disease", "outbreak", "epidemic", "hospital", "contamination"],
            "terrorism": ["bomb", "terror", "explosive", "suicide", "militant"],
            "cyber": ["hack", "cyber", "ransomware", "breach", "malware"],
            "armed_conflict": ["militia", "airstrike", "rocket", "sniper", "armed", "military"],
        }

    async def initialize(self) -> None:
        """Load all models. Safe to call multiple times — only loads once."""
        if self._initialized:
            return
        logger.info("Initializing NLP pipeline (this may take a moment)...")
        t0 = time.time()
        await self._load_spacy()
        await self._load_sentiment()
        await self._load_classifier()
        await self._load_keywords()
        self._initialized = True
        logger.info("NLP pipeline ready in %.1fs", time.time() - t0)

    async def _load_spacy(self) -> None:
        try:
            import spacy
            self._nlp_en = spacy.load("en_core_web_lg")
            logger.info("spaCy en_core_web_lg loaded")
        except Exception as exc:
            logger.warning("spaCy English model unavailable: %s", exc)
        try:
            import spacy
            self._nlp_xx = spacy.load("xx_ent_wiki_sm")
            logger.info("spaCy xx_ent_wiki_sm loaded")
        except Exception as exc:
            logger.warning("spaCy multilingual model unavailable: %s", exc)

    async def _load_sentiment(self) -> None:
        try:
            from transformers import pipeline as hf_pipeline
            self._sentiment_en = hf_pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                top_k=1,
            )
            logger.info("HuggingFace EN sentiment model loaded")
        except Exception as exc:
            logger.warning("EN sentiment model unavailable: %s", exc)

        try:
            from transformers import pipeline as hf_pipeline
            self._sentiment_ar = hf_pipeline(
                "sentiment-analysis",
                model="aubmindlab/bert-base-arabertv2",
                top_k=1,
            )
            logger.info("HuggingFace AR sentiment model loaded")
        except Exception as exc:
            logger.warning("AR sentiment model unavailable: %s", exc)

    async def _load_classifier(self) -> None:
        try:
            from transformers import pipeline as hf_pipeline
            self._classifier = hf_pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
            )
            logger.info("Zero-shot classifier (bart-large-mnli) loaded")
        except Exception as exc:
            logger.warning("Zero-shot classifier unavailable: %s", exc)

    async def _load_keywords(self) -> None:
        try:
            from app.db.redis import redis_client
            self._keywords = await redis_client.get_threat_keywords()
            logger.info("Loaded %d threat keywords from Redis", len(self._keywords))
        except Exception as exc:
            logger.warning("Could not load threat keywords from Redis: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    async def process(self, text: str, metadata: Optional[dict] = None) -> dict[str, Any]:
        """
        Process raw text through the full NLP pipeline.

        Returns enriched dict with:
          language, cleaned_text, entities, sentiment_score, emotion,
          category, category_confidence, keyword_score, keywords
        """
        if not self._initialized:
            await self.initialize()

        result: dict[str, Any] = {
            "language": "unknown",
            "cleaned_text": "",
            "entities": [],
            "keywords": [],
            "sentiment_score": 0.0,
            "emotion": "neutral",
            "category": "other",
            "category_confidence": 0.0,
            "keyword_score": 0.0,
        }

        if not text or not text.strip():
            return result

        # Step 1: Language detection
        result["language"] = self._detect_language(text)

        # Step 2: Text cleaning
        cleaned = _clean_text(text)
        if result["language"] == "ar":
            cleaned = _normalize_arabic(cleaned)
        result["cleaned_text"] = cleaned

        # Step 3: NER
        t0 = time.time()
        result["entities"] = self._extract_entities(cleaned, result["language"])
        logger.debug("NER: %.2fs — %d entities", time.time() - t0, len(result["entities"]))

        # Step 4: Sentiment
        t0 = time.time()
        sentiment_result = self._analyze_sentiment(cleaned, result["language"])
        result["sentiment_score"] = sentiment_result["score"]
        result["emotion"] = sentiment_result["emotion"]
        logger.debug("Sentiment: %.2fs — %.3f", time.time() - t0, result["sentiment_score"])

        # Step 5: Topic classification
        t0 = time.time()
        classification = self._classify_topic(cleaned, result["language"])
        result["category"] = classification["category"]
        result["category_confidence"] = classification["confidence"]
        logger.debug(
            "Classification: %.2fs — %s (%.2f)",
            time.time() - t0,
            result["category"],
            result["category_confidence"],
        )

        # Step 6: Keyword scoring
        t0 = time.time()
        kw_result = self._score_keywords(cleaned)
        result["keyword_score"] = kw_result["score"]
        result["keywords"] = kw_result["matched"]
        logger.debug("Keywords: %.2fs — score=%.2f", time.time() - t0, result["keyword_score"])

        return result

    def _detect_language(self, text: str) -> str:
        """Detect text language. Returns ISO 639-1 code or 'unknown'."""
        try:
            from langdetect import detect
            lang = detect(text)
            return {"ar": "ar", "en": "en", "fr": "fr"}.get(lang, lang)
        except Exception:
            # Heuristic: if > 20% Arabic Unicode chars → Arabic
            arabic = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
            if arabic / max(len(text), 1) > 0.2:
                return "ar"
            return "en"

    def _extract_entities(self, text: str, language: str) -> list[dict[str, str]]:
        """Run spaCy NER and return structured entity list."""
        entities: list[dict[str, str]] = []
        model = (self._nlp_xx if language == "ar" else self._nlp_en) or self._nlp_xx or self._nlp_en
        if not model:
            return entities
        try:
            doc = model(text[:5000])
            for ent in doc.ents:
                entities.append({"text": ent.text, "label": ent.label_})
        except Exception as exc:
            logger.debug("spaCy NER failed: %s", exc)
        return entities

    def _analyze_sentiment(self, text: str, language: str) -> dict[str, Any]:
        """Run HuggingFace sentiment. Returns score in [-1, 1] + emotion label."""
        pipeline = self._sentiment_ar if language == "ar" else self._sentiment_en
        if pipeline:
            try:
                result = pipeline(text[:512], truncation=True)
                item = result[0] if isinstance(result, list) and result else {}
                if isinstance(item, list):
                    item = item[0]
                label = item.get("label", "NEUTRAL").upper()
                raw_score = float(item.get("score", 0.5))
                if "NEGATIVE" in label or "NEG" in label or label == "0":
                    return {"score": -round(raw_score, 4), "emotion": "anger" if raw_score > 0.7 else "sadness"}
                elif "POSITIVE" in label or "POS" in label or label == "2":
                    return {"score": round(raw_score, 4), "emotion": "hope"}
                return {"score": 0.0, "emotion": "neutral"}
            except Exception as exc:
                logger.debug("HuggingFace sentiment failed: %s", exc)

        # Fallback: keyword-based sentiment
        neg_words = {"attack", "shooting", "explosion", "bomb", "dead", "injured", "kill",
                     "انفجار", "هجوم", "قتيل", "جريح", "إطلاق"}
        words = set(text.lower().split())
        neg_count = len(words & neg_words)
        score = max(-1.0, -0.2 * neg_count)
        return {"score": round(score, 4), "emotion": "neutral" if score == 0 else "anger"}

    def _classify_topic(self, text: str, language: str = "en") -> dict[str, Any]:
        """Zero-shot classify into incident categories. Falls back to keyword matching."""
        if self._classifier:
            try:
                result = self._classifier(text[:512], candidate_labels=CATEGORY_LABELS, truncation=True)
                top_label = result["labels"][0]
                top_score = float(result["scores"][0])
                category = CATEGORY_MAP.get(top_label, "other")
                return {"category": category, "confidence": round(top_score, 4)}
            except Exception as exc:
                logger.debug("Zero-shot classification failed: %s", exc)

        # Fallback: keyword matching
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for cat, words in self.category_keywords.items():
            scores[cat] = sum(1 for w in words if w in text_lower)
        if scores:
            best = max(scores, key=lambda k: scores[k])
            if scores[best] > 0:
                return {"category": best, "confidence": min(0.7, 0.2 * scores[best])}
        return {"category": "other", "confidence": 0.0}

    def _score_keywords(self, text: str) -> dict[str, Any]:
        """Score text against threat keyword dictionary."""
        if not self._keywords:
            # Fallback to legacy keyword dict
            text_lower = text.lower()
            matched = []
            score = 0.0
            for cat, words in self.category_keywords.items():
                for w in words:
                    if w in text_lower:
                        matched.append(w)
                        score += 5.0
            return {"score": min(100.0, score), "matched": matched[:20]}

        text_lower = text.lower()
        total = 0.0
        matched: list[str] = []
        for keyword, weight in self._keywords.items():
            if keyword.lower() in text_lower:
                total += weight
                matched.append(keyword)
        return {"score": round(min(100.0, (total / 50.0) * 100.0), 2), "matched": matched[:20]}

    def get_gpe_entities(self, entities: list[dict[str, str]]) -> list[str]:
        """Extract GPE (geopolitical entity) strings from NER output."""
        return [e["text"] for e in entities if e.get("label") in ("GPE", "LOC")]


# Singleton
nlp_pipeline = NLPPipeline()
