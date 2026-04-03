"""Anomaly Detection Service — Section 6.2.

Uses Isolation Forest trained on historical feature vectors.
Features: [sentiment_mean, volume_zscore, keyword_score, behavior_score, geo_density]
Anomaly threshold: score < -0.5

Retrained weekly on last 30 days of data via Celery scheduled task.
"""
from __future__ import annotations

import logging
import pickle
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parents[2] / "ml-pipeline" / "models" / "anomaly_detector.pkl"


class AnomalyDetector:
    """Isolation Forest anomaly detector for risk feature vectors."""

    def __init__(self) -> None:
        self._model = None
        self._trained_at: Optional[datetime] = None

    @property
    def is_trained(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        """Load pre-trained model from disk."""
        if MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    saved = pickle.load(f)
                self._model = saved["model"]
                self._trained_at = saved.get("trained_at")
                logger.info("Anomaly detector loaded (trained %s)", self._trained_at)
                return True
            except Exception as exc:
                logger.warning("Failed to load anomaly detector: %s", exc)
        return False

    def train(self, feature_vectors: list[list[float]]) -> None:
        """Train Isolation Forest on feature vectors.

        feature_vectors: list of [sentiment, volume, keyword, behavior, geospatial]
        """
        if len(feature_vectors) < 10:
            logger.warning("Not enough samples to train anomaly detector (%d)", len(feature_vectors))
            return

        try:
            from sklearn.ensemble import IsolationForest
            import numpy as np

            X = np.array(feature_vectors)
            self._model = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42,
                n_jobs=-1,
            )
            self._model.fit(X)
            self._trained_at = datetime.now(UTC)

            # Save to disk
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MODEL_PATH, "wb") as f:
                pickle.dump({"model": self._model, "trained_at": self._trained_at}, f)

            logger.info("Anomaly detector trained on %d samples", len(feature_vectors))
        except Exception as exc:
            logger.error("Anomaly detector training failed: %s", exc)

    def predict(self, feature_vectors: list[list[float]]) -> dict:
        """
        Returns:
            { is_anomalous: bool, score: float }  (-1 = anomalous, 1 = normal in sklearn)
        """
        if not self._model:
            return {"is_anomalous": False, "score": 0.0}

        try:
            import numpy as np

            X = np.array(feature_vectors)
            scores = self._model.score_samples(X)
            predictions = self._model.predict(X)

            # sklearn: -1 = anomaly, 1 = normal
            is_anomalous = bool(predictions[0] == -1)
            raw_score = float(scores[0])
            return {"is_anomalous": is_anomalous, "score": round(raw_score, 4)}
        except Exception as exc:
            logger.debug("Anomaly detection prediction failed: %s", exc)
            return {"is_anomalous": False, "score": 0.0}

    async def train_from_incidents(self) -> None:
        """Build training data from last 30 days of incidents and retrain."""
        try:
            from app.services.feature_engineering import feature_engineering_service
            from app.services.local_store import local_store

            now = datetime.now(UTC)
            cutoff = now - timedelta(days=30)
            incidents = [
                i for i in local_store.list_incidents()
                if i.created_at >= cutoff
            ]

            if not incidents:
                logger.info("No incidents in last 30 days for anomaly retraining")
                return

            # Build daily feature vectors
            features_by_region = feature_engineering_service.build_region_features(incidents, now=now)
            vectors = [
                feature_engineering_service.build_feature_vector(f)
                for f in features_by_region.values()
            ]

            if vectors:
                self.train(vectors)
        except Exception as exc:
            logger.error("Anomaly retraining failed: %s", exc)


anomaly_detector = AnomalyDetector()
# Try to load saved model on import
anomaly_detector.load()
