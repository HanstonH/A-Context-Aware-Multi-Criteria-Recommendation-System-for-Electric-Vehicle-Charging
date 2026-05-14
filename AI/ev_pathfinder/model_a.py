"""Model A — Station Availability Classification.

Loads the grid-searched classifiers (XGBoost, Random Forest, Decision Tree,
Logistic Regression) and returns per-model availability predictions with
probability estimates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import joblib
import numpy as np

from .config import MODEL_A_DIR


@dataclass
class AvailabilityPrediction:
    model_name: str
    available: bool
    probability: float     # P(available)
    confidence: str        # "high" / "medium" / "low"


def _confidence_label(prob: float) -> str:
    margin = abs(prob - 0.5)
    if margin >= 0.3:
        return "high"
    if margin >= 0.15:
        return "medium"
    return "low"


class ModelAService:
    """Loads and serves the availability classification models."""

    _MODEL_FILES = {
        "XGBoost": "best_xgb_model.pkl",
        "Random Forest": "best_rf_model.pkl",
        "Decision Tree": "best_dt_model.pkl",
        "Logistic Regression": "best_lr_model.pkl",
    }

    def __init__(self):
        self.models: Dict[str, object] = {}
        self._load()

    def _load(self) -> None:
        for name, filename in self._MODEL_FILES.items():
            path = MODEL_A_DIR / filename
            if path.exists():
                try:
                    self.models[name] = joblib.load(str(path))
                except Exception as exc:
                    print(f"[Model A] Failed to load {name}: {exc}")

    @property
    def loaded(self) -> bool:
        return len(self.models) > 0

    def predict(self, features: np.ndarray) -> List[AvailabilityPrediction]:
        results: List[AvailabilityPrediction] = []
        for name, model in self.models.items():
            try:
                pred = model.predict(features)[0]
                available = bool(pred < 0.5)  # 0 = available, 1 = occupied

                prob_avail = 1.0 - float(pred)
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(features)[0]
                    prob_avail = float(proba[0]) if len(proba) > 1 else float(1 - proba[0])

                results.append(AvailabilityPrediction(
                    model_name=name,
                    available=available,
                    probability=round(prob_avail, 4),
                    confidence=_confidence_label(prob_avail),
                ))
            except Exception as exc:
                print(f"[Model A] {name} prediction error: {exc}")

        return results

    def predict_consensus(self, features: np.ndarray) -> Optional[AvailabilityPrediction]:
        """Majority-vote across all loaded models."""
        preds = self.predict(features)
        if not preds:
            return None
        votes_available = sum(1 for p in preds if p.available)
        consensus_available = votes_available > len(preds) / 2
        avg_prob = np.mean([p.probability for p in preds])
        return AvailabilityPrediction(
            model_name="Ensemble (majority vote)",
            available=consensus_available,
            probability=round(float(avg_prob), 4),
            confidence=_confidence_label(float(avg_prob)),
        )
