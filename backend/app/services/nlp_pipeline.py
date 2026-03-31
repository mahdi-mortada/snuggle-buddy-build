from __future__ import annotations

import re


class NLPPipeline:
    def __init__(self) -> None:
        self.category_keywords: dict[str, list[str]] = {
            "violence": ["shooting", "attack", "roadblock", "clash"],
            "protest": ["protest", "crowd", "march", "demonstration"],
            "natural_disaster": ["flood", "earthquake", "storm", "rain"],
            "infrastructure": ["power", "outage", "grid", "water"],
            "health": ["clinic", "hospital", "illness", "respiratory"],
            "terrorism": ["suspicious", "explosive", "package", "bomb"],
            "cyber": ["cyber", "phishing", "malware", "network"],
        }

    def analyze(self, text: str) -> dict[str, object]:
        cleaned = re.sub(r"\s+", " ", text).strip()
        lowered = cleaned.lower()
        category = "other"
        keywords: list[str] = []

        for candidate, tokens in self.category_keywords.items():
            matches = [token for token in tokens if token in lowered]
            if matches:
                category = candidate
                keywords = matches
                break

        sentiment = -0.65 if any(token in lowered for token in ["attack", "critical", "outage", "flood", "suspicious"]) else -0.2
        severity = "critical" if any(token in lowered for token in ["critical", "attack", "suspicious", "outage"]) else "medium"
        entities = re.findall(r"\b[A-Z][a-zA-Z'-]+\b", cleaned)

        return {
            "cleaned_text": cleaned,
            "category": category,
            "severity": severity,
            "sentiment_score": sentiment,
            "keywords": keywords,
            "entities": entities[:8],
        }


nlp_pipeline = NLPPipeline()
