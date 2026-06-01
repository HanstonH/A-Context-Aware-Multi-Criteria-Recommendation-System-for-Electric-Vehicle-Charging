"""Model B service for charging-session duration prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import joblib
import numpy as np

from config import MODEL_B_DIR


@dataclass
class DurationPrediction:
    model_name: str
    duration_secs: float
    duration_mins: float


class ModelBService:
    """Loads and serves the duration prediction models."""

    _MODEL_FILES = {
        "XGBoost": "best_xgb_model.pkl",
        "Random Forest": "best_rf_model.pkl",
        "Decision Tree": "best_dt_model.pkl",
        "Logistic Regression": "best_lr_model.pkl",
    }

    _LSTM_KERAS = "lstm_duration.keras"
    _LSTM_PKL = "lstm.pkl"

    def __init__(self):
        self.models: Dict[str, object] = {}
        self.lstm_model = None
        self._is_regressor: Dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        for name, filename in self._MODEL_FILES.items():
            path = MODEL_B_DIR / filename
            if path.exists():
                try:
                    model = joblib.load(str(path))
                    self.models[name] = model
                    self._is_regressor[name] = (
                        hasattr(model, "predict") and not hasattr(model, "predict_proba")
                    ) or (
                        hasattr(model, "_estimator_type") and model._estimator_type == "regressor"
                    )
                except Exception as exc:
                    print(f"[Model B] Failed to load {name}: {exc}")

        keras_path = MODEL_B_DIR / self._LSTM_KERAS
        pkl_path = MODEL_B_DIR / self._LSTM_PKL
        if keras_path.exists():
            try:
                import tensorflow as tf
                self.lstm_model = tf.keras.models.load_model(str(keras_path))
            except Exception as exc:
                print(f"[Model B] LSTM Keras load failed: {exc}")
        elif pkl_path.exists():
            try:
                self.lstm_model = joblib.load(str(pkl_path))
            except Exception as exc:
                print(f"[Model B] LSTM pkl load failed: {exc}")

    @property
    def loaded(self) -> bool:
        return len(self.models) > 0

    def predict(self, features: np.ndarray) -> List[DurationPrediction]:
        results: List[DurationPrediction] = []
        for name, model in self.models.items():
            try:
                raw = model.predict(features)[0]
                secs = max(float(raw), 0.0)
                if not self._is_regressor.get(name, True) and secs <= 1.0:
                    continue
                results.append(DurationPrediction(
                    model_name=name,
                    duration_secs=round(secs, 1),
                    duration_mins=round(secs / 60, 1),
                ))
            except Exception as exc:
                print(f"[Model B] {name} prediction error: {exc}")
        return results

    def predict_lstm(self, sequence: np.ndarray) -> Optional[DurationPrediction]:
        if self.lstm_model is None:
            return None
        try:
            raw = self.lstm_model.predict(sequence, verbose=0)[0][0]
            secs = max(float(raw), 0.0)
            return DurationPrediction(
                model_name="LSTM",
                duration_secs=round(secs, 1),
                duration_mins=round(secs / 60, 1),
            )
        except Exception as exc:
            print(f"[Model B] LSTM prediction error: {exc}")
            return None

    def predict_ensemble(self, features: np.ndarray) -> Optional[DurationPrediction]:
        preds = self.predict(features)
        if not preds:
            return None
        avg_secs = np.mean([pred.duration_secs for pred in preds])
        return DurationPrediction(
            model_name="Ensemble (average)",
            duration_secs=round(float(avg_secs), 1),
            duration_mins=round(float(avg_secs) / 60, 1),
        )
