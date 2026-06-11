"""Model A -- Station Availability Classification.

Loads the grid-searched classifiers (XGBoost, Random Forest, Decision Tree,
Logistic Regression) **and** the LSTM (sequence-based) model.

Availability Threshold
----------------------
Training labels:  0 = Available, 1 = Occupied.

*Classifiers* output a hard class (0/1) via ``predict()`` and
``predict_proba()`` returns ``[P(class 0), P(class 1)]``.

The *LSTM* outputs a sigmoid value in [0, 1] that represents
P(Occupied).  We compare it against ``AVAILABILITY_THRESHOLD``
(default 0.5):

    sigmoid_output < threshold  =>  Available
    sigmoid_output >= threshold =>  Occupied

Adjust the threshold in ``config.py`` to trade off false-positives
(sending users to a busy station) vs false-negatives (telling users
to wait when the station is actually free).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import joblib
import numpy as np

from .config import AVAILABILITY_THRESHOLD, MODEL_A_DIR


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

    _LSTM_PKL = "lstm.pkl"

    def __init__(self):
        self.models: Dict[str, object] = {}
        self.lstm_model = None
        self._load()

    def _load(self) -> None:
        for name, filename in self._MODEL_FILES.items():
            path = MODEL_A_DIR / filename
            if path.exists():
                try:
                    self.models[name] = joblib.load(str(path))
                except Exception as exc:
                    print(f"[Model A] Failed to load {name}: {exc}")

        lstm_path = MODEL_A_DIR / self._LSTM_PKL
        if lstm_path.exists():
            try:
                self.lstm_model = joblib.load(str(lstm_path))
            except Exception as exc:
                print(f"[Model A] LSTM load failed: {exc}")

    @property
    def loaded(self) -> bool:
        return len(self.models) > 0

    @property
    def lstm_loaded(self) -> bool:
        return self.lstm_model is not None

    def predict(self, features: np.ndarray) -> List[AvailabilityPrediction]:
        results: List[AvailabilityPrediction] = []
        for name, model in self.models.items():
            try:
                pred = model.predict(features)[0]
                available = bool(pred < AVAILABILITY_THRESHOLD)

                prob_avail = 1.0 - float(pred)
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(features)[0]
                    prob_avail = float(proba[0]) if len(proba) > 1 else float(1 - proba[0])

                results.append(AvailabilityPrediction(
                    model_name=name,
                    available=prob_avail > AVAILABILITY_THRESHOLD,
                    probability=round(prob_avail, 4),
                    confidence=_confidence_label(prob_avail),
                ))
            except Exception as exc:
                print(f"[Model A] {name} prediction error: {exc}")

        return results

    def predict_lstm(self, sequence: np.ndarray) -> Optional[AvailabilityPrediction]:
        """Run the LSTM on a (1, 12, 15) sequence array.

        The sigmoid output represents P(Occupied).
        Available when output < AVAILABILITY_THRESHOLD.
        """
        if self.lstm_model is None:
            return None
        try:
            raw = float(self.lstm_model.predict(sequence, verbose=0)[0][0])
            prob_available = 1.0 - raw
            available = raw < AVAILABILITY_THRESHOLD
            return AvailabilityPrediction(
                model_name="LSTM",
                available=available,
                probability=round(prob_available, 4),
                confidence=_confidence_label(prob_available),
            )
        except Exception as exc:
            print(f"[Model A] LSTM prediction error: {exc}")
            return None

    def predict_consensus(self, features: np.ndarray) -> Optional[AvailabilityPrediction]:
        """Majority-vote across all loaded traditional models."""
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
