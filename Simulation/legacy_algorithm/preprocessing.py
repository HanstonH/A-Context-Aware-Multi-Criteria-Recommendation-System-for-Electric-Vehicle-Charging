"""Feature preprocessing for algorithm wait-time inference."""

from __future__ import annotations

from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, TargetEncoder

from config import CLEANED_DATA_PATH, PREPROCESSOR_PATH


class InferencePreprocessor:
    """Loads or fits the preprocessing pipeline used during wait-time inference."""

    def __init__(self):
        self._pipeline_a: Optional[Pipeline] = None
        self._pipeline_b: Optional[Pipeline] = None
        self._original_columns: list[str] = []

    def _fit_from_data(self, target_col: str) -> Pipeline:
        df = pd.read_csv(str(CLEANED_DATA_PATH), low_memory=False)
        target = df[target_col].copy()
        feature_df = df.drop(
            columns=[c for c in ("Availability", "Total_Duration_Secs") if c in df.columns],
        )

        self._original_columns = list(feature_df.columns)
        num_attribs = [c for c in feature_df.select_dtypes(include="number").columns]
        cat_attribs = ["MAC Address"]

        preprocessor = ColumnTransformer(
            transformers=[
                ("mac_target", TargetEncoder(), cat_attribs),
                ("std_scaler", StandardScaler(), num_attribs),
            ],
            remainder="passthrough",
        )

        pipe = Pipeline([("preprocessor", preprocessor)])
        pipe.fit(feature_df, target)
        return pipe

    def _get_pipeline(self, model_type: str) -> Pipeline:
        if model_type == "availability":
            if self._pipeline_a is None:
                self._pipeline_a = self._fit_from_data("Availability")
            return self._pipeline_a

        if self._pipeline_b is None:
            self._pipeline_b = self._load_binary_encoder_pipeline()
        return self._pipeline_b

    def _load_binary_encoder_pipeline(self) -> Pipeline:
        if PREPROCESSOR_PATH.exists():
            return joblib.load(str(PREPROCESSOR_PATH))
        raise FileNotFoundError(
            f"Model B preprocessor not found at {PREPROCESSOR_PATH}. "
            "Ensure preprocessor_pipeline.joblib exists in Algorithm/."
        )

    def transform(
        self,
        raw_df: pd.DataFrame,
        model_type: str = "availability",
    ) -> pd.DataFrame:
        pipe = self._get_pipeline(model_type)
        transformed = pipe.transform(raw_df)
        arr = np.asarray(transformed)

        if model_type == "availability" and self._original_columns:
            cols = self._original_columns
        else:
            try:
                ct = pipe.named_steps.get("preprocessor", pipe)
                cols = list(ct.get_feature_names_out())
            except Exception:
                cols = [f"f{i}" for i in range(arr.shape[1])]
        return pd.DataFrame(arr, columns=cols)
