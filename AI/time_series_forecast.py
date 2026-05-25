"""OOP migration of the Time Series Forecast notebook.

The original notebook functions are kept intact and exposed at module level.
Use ``TimeSeriesForecastPipeline`` to run the workflow in an object-oriented way.
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from pandas.tseries.holiday import USFederalHolidayCalendar
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import GridSearchCV, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, TargetEncoder
from sklearn.tree import DecisionTreeClassifier

try:
    import xgboost as xgb
except ModuleNotFoundError:
    xgb = None


def normalize_available_flag(available):
    if isinstance(available, str):
        return available.strip().lower() not in {"false", "0", "no", "n", "duration", "wait_time", "waiting_time"}
    return bool(available)


# --- 1. WEATHER UTILITY ---
def get_palo_alto_weather(start_date, end_date):
    """Fetches hourly historical weather for Palo Alto from Open-Meteo."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 37.4419,
        "longitude": -122.1430,
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
        "hourly": ["temperature_2m", "precipitation", "cloudcover"],
        "timezone": "America/Los_Angeles"
    }
    try:
        response = requests.get(url, params=params)
        res_data = response.json()
        weather_df = pd.DataFrame({
            'weather_time': pd.to_datetime(res_data['hourly']['time']),
            'temp': res_data['hourly']['temperature_2m'],
            'precip': res_data['hourly']['precipitation'],
            'clouds': res_data['hourly']['cloudcover']
        })
        return weather_df
    except Exception as e:
        print(f"Weather API error: {e}. Returning empty DF.")
        return pd.DataFrame()

# --- 2. TIME UTILITIES ---
def to_seconds_vectorized(series):
    """Converts hh:mm:ss to total seconds."""
    temp = series.str.split(':', expand=True).astype(float)
    return (temp[0] * 3600) + (temp[1] * 60) + temp[2]

def engineer_time_features(df):
    """Extracts temporal signals and handles cyclical encoding."""
    # Ensure datetime format for extraction
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    
    # 1. Basic Extraction
    df['Minute'] = df['Start Date'].dt.minute
    df['Hour'] = df['Start Date'].dt.hour
    df['DayOfWeek'] = df['Start Date'].dt.dayofweek
    df['Month'] = df['Start Date'].dt.month
    df['IsWeekend'] = (df['DayOfWeek'] >= 5).astype(int)
    
    # 2. Holiday Lookup (US)
    cal = USFederalHolidayCalendar()
    holidays = cal.holidays(start=df['Start Date'].min(), end=df['Start Date'].max())
    df['IsHoliday'] = df['Start Date'].dt.normalize().isin(holidays).astype(int)
    
    # 3. Cyclical Encoding (Neural Network friendly)
    df['Hour_Sin'] = np.sin(2 * np.pi * df['Hour'] / 24)
    df['Hour_Cos'] = np.cos(2 * np.pi * df['Hour'] / 24)
    df['Month_Sin'] = np.sin(2 * np.pi * df['Month'] / 12)
    df['Month_Cos'] = np.cos(2 * np.pi * df['Month'] / 12)
    
    return df

def add_real_time_metadata(df, raw_data):
    # 1. Station Density (How many chargers at this physical location?)
    # This is a static "Right Now" input.
    addr_map = raw_data.groupby('Address 1')['MAC Address'].nunique().to_dict()
    df['Station_Density'] = df['Address 1'].map(addr_map)

    # 2. Pricing Signal (Is it free?)
    # Paid stations have different turnover rates.
    fee_map = raw_data.groupby('MAC Address')['Fee'].mean().apply(lambda x: 1 if x > 0 else 0).to_dict()
    df['Is_Paid_Station'] = df['MAC Address'].map(fee_map)
    
    # Need to be calculated on training set
    # hist_stats = df.groupby(['MAC Address', 'DayOfWeek', 'Hour'])['Availability'].mean().reset_index()
    # hist_stats.rename(columns={'Availability': 'Hist_Occupancy_Prob'}, inplace=True)
    # df = df.merge(hist_stats, on=['MAC Address', 'DayOfWeek', 'Hour'], how='left')
    
    return df
    
# --- 3. MAIN PIPELINE ---
def build_final_dataset(data, available=True):
    """Processes raw sessions, adds availability gaps, merges weather, and balances classes."""
    available = normalize_available_flag(available)
    df = data.copy()
    df['Start Date'] = pd.to_datetime(df['Start Date'])
    df['End Date'] = pd.to_datetime(df['End Date'])
    
    # Sort for gap detection
    full_df = df.sort_values(['MAC Address', 'Start Date'])
    
    # A. Extract Occupied Sessions (Label 1)
    full_df = df[['MAC Address', 'Start Date', 'End Date', 'Plug Type', 'Address 1']].copy()
    full_df['Total_Duration_Secs'] = to_seconds_vectorized(df['Total Duration (hh:mm:ss)'])
    
    
    # B. Generate Available Sessions (Label 0)
    if available:
        full_df['Availability'] = 1
        available_rows = []
        for mac, group in df.groupby('MAC Address'):
            group = group.sort_values('Start Date')
            for i in range(len(group) - 1):
                curr_end = group.iloc[i]['End Date']
                next_start = group.iloc[i+1]['Start Date']
                
                # Identify idle gaps longer than 5 mins
                if next_start > curr_end + pd.Timedelta(minutes=5):
                    available_rows.append({
                        'MAC Address': mac,
                        'Start Date': curr_end,
                        'End Date': next_start,
                        'Plug Type': group.iloc[i]['Plug Type'],
                        'Address 1': group.iloc[i]['Address 1'],
                        'Total_Duration_Secs': (next_start - curr_end).total_seconds(),
                        'Availability': 0
                    })
        
            available_df = pd.DataFrame(available_rows)
    
        # C. Random Undersampling for 50/50 Balance
        n_min = min(len(full_df), len(available_df))
        occupied_balanced = full_df.sample(n=n_min, random_state=42)
        available_balanced = available_df.sample(n=n_min, random_state=42)
        
        full_df = pd.concat([occupied_balanced, available_balanced], ignore_index=True)
    full_df = full_df.sort_values('Start Date').reset_index(drop=True)
    
    # D. Integrate Weather
    print("Fetching Palo Alto weather data...")
    weather = get_palo_alto_weather(full_df['Start Date'].min(), full_df['Start Date'].max())
    
    if not weather.empty:
        # Use 'h' for hourly floor (Pandas 3.0+ compatibility)
        full_df['merge_hour'] = full_df['Start Date'].dt.floor('h')
        full_df = full_df.merge(weather, left_on='merge_hour', right_on='weather_time', how='left')
        full_df.drop(columns=['merge_hour', 'weather_time'], inplace=True)
    
    # E. Feature Engineering
    full_df = engineer_time_features(full_df)
    
    # F. Encode Categoricals
    full_df['Plug Type Encoded'] = full_df['Plug Type'].map({'J1772': 0, 'NEMA 5-20R': 1}).fillna(0).astype(int)
    
    # G. Add static metadata before dropping address/session columns
    # This reduces the accuracy so remove for now
    # full_df = add_real_time_metadata(full_df, data)
    
    # H. Final Cleanup
    cols_to_drop = ['Start Date', 'End Date', 'Plug Type', 'Address 1']
    final_df = full_df.drop(columns=cols_to_drop).fillna(full_df.mean(numeric_only=True))
    
    print(f"Final dataset shape: {final_df.shape}")
    if 'Availability' in final_df.columns:
        print(f"Class distribution:\n{final_df['Availability'].value_counts()}")
    else:
        print(f"Duration target summary:\n{final_df['Total_Duration_Secs'].describe()}")
    
    
    return final_df

# Example Usage:
# final_data = build_final_dataset(raw_csv_data)


class CustomAttributeTransformer(BaseEstimator, TransformerMixin):
    def __init__(self, verbose=False):
        self.verbose = verbose
    def fit(self, X, y=None):
        return self
    def transform(self, data):
        data_copy = data.copy()

        if self.verbose:
            print(data_copy)
        return data_copy


def create_grouped_sequences(df, feature_cols, target_col, time_steps=12):
    X, y = [], []
    
    # Group by MAC address to ensure charger histories don't mix
    for mac, group in df.groupby('MAC Address'):
        # Extract the features and target for this specific charger
        group_features = group[feature_cols].values
        group_target = group[target_col].values
        
        # Only create sequences if the charger has enough data
        if len(group_features) > time_steps:
            for i in range(len(group_features) - time_steps):
                X.append(group_features[i : (i + time_steps)])
                y.append(group_target[i + time_steps])
    
    return np.array(X), np.array(y)


@dataclass
class TimeSeriesForecastConfig:
    data_path: str = "data/ChargePointData2011-2020-ManullyPreCleaned3.csv"
    model_dir: str = "model"
    test_size: float = 0.2
    random_state: int = 42
    time_steps: int = 12
    verbose: bool = False


class TimeSeriesForecastPipeline:
    """Object-oriented wrapper around the original notebook workflow."""

    def __init__(self, config: Optional[TimeSeriesForecastConfig] = None):
        self.config = config or TimeSeriesForecastConfig()
        self.data: Optional[pd.DataFrame] = None
        self.final_df: Optional[pd.DataFrame] = None
        self.available: bool = True
        self.target_column: str = "Availability"
        self.train_df: Optional[pd.DataFrame] = None
        self.test_df: Optional[pd.DataFrame] = None
        self.train_df_label_availability: Optional[pd.Series] = None
        self.train_df_label_duration: Optional[pd.Series] = None
        self.training_label: Optional[pd.Series] = None
        self.train_df_data: Optional[pd.DataFrame] = None
        self.test_df_data: Optional[pd.DataFrame] = None
        self.testing_label: Optional[pd.Series] = None
        self.full_pipeline: Optional[Pipeline] = None
        self.training_dataset: Optional[pd.DataFrame] = None
        self.testing_dataset: Optional[pd.DataFrame] = None
        self.testing_data_final: Optional[np.ndarray] = None
        self.best_results: Dict[str, Dict[str, object]] = {}
        self.models: Dict[str, object] = {}
        self.voting_clf: Optional[VotingClassifier] = None
        self.X_final: Optional[np.ndarray] = None
        self.y_final: Optional[np.ndarray] = None
        self.X_test_seq: Optional[np.ndarray] = None
        self.y_test_seq: Optional[np.ndarray] = None
        self.lstm_model = None

    def load_data(self) -> pd.DataFrame:
        self.data = pd.read_csv(self.config.data_path, low_memory=False)
        return self.data

    def build_dataset(self, available=True) -> pd.DataFrame:
        if self.data is None:
            self.load_data()
        available = normalize_available_flag(available)
        self.available = available
        self.target_column = "Availability" if available else "Total_Duration_Secs"
        self.final_df = build_final_dataset(self.data, available=available)
        return self.final_df

    def split_dataset(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if self.final_df is None:
            self.build_dataset()
        split_idx = int(len(self.final_df) * (1 - self.config.test_size))
        self.train_df = self.final_df.iloc[:split_idx]
        self.test_df = self.final_df.iloc[split_idx:]
        return self.train_df, self.test_df

    def separate_train_labels(self, available=None) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
        if self.train_df is None:
            self.split_dataset()

        if available is None:
            available = self.available
        available = normalize_available_flag(available)
        
        if available:
            self.train_df_label_availability = (
                self.train_df['Availability'].copy()
                if 'Availability' in self.train_df.columns
                else None
        )
        else:
            self.train_df_label_duration = (
                self.train_df['Total_Duration_Secs'].copy()
                if 'Total_Duration_Secs' in self.train_df.columns
                else None
            )
        drop_cols = [col for col in ['Availability','Total_Duration_Secs'] if col in self.train_df.columns]
        self.train_df_data = self.train_df.drop(drop_cols, axis = 1)
        self.training_label = self.get_train_target()
        return self.train_df_data, self.train_df_label_availability, self.train_df_label_duration

    def get_train_target(self) -> pd.Series:
        if self.train_df is None:
            self.split_dataset()
        if self.target_column not in self.train_df.columns:
            raise KeyError(f"Target column '{self.target_column}' is missing from the training data.")
        return self.train_df[self.target_column].copy()

    def build_preprocessor(self) -> Pipeline:
        if self.train_df_data is None:
            self.separate_train_labels()

        num_attribs = list(self.train_df_data.select_dtypes(include="number").columns)
        cat_attribs = ['MAC Address']
        if self.config.verbose:
            print(num_attribs)

        preprocessor = ColumnTransformer(
            transformers=[
                # 1. Target Encode ONLY the MAC Address
                ('mac_target', TargetEncoder(), cat_attribs),
                
                # 2. Scale the numerical/cyclical features
                ('std_scaler', StandardScaler(), num_attribs)
            ],
            # 3. Important: 'passthrough' keeps columns like IsWeekend/IsHoliday 
            # that are already binary/numeric without changing them.
            remainder='passthrough' 
        )

        self.full_pipeline = Pipeline([
            ('custom', CustomAttributeTransformer(verbose=self.config.verbose)),
            ('preprocessor', preprocessor)
        ])
        
        preprocessor.set_output(transform="pandas")
        
        return self.full_pipeline

    def prepare_training_dataset(self) -> pd.DataFrame:
        started_at = time.perf_counter()
        if self.full_pipeline is None:
            self.build_preprocessor()
        train_target = self.get_train_target()
        self.training_label = train_target
        if self.config.verbose:
            print(f"Preparing training data: {self.train_df_data.shape[0]} rows, {self.train_df_data.shape[1]} columns")
        transformed = self.full_pipeline.fit_transform(
            self.train_df_data,
            train_target,
        )
        self.training_dataset = self._as_feature_frame(transformed, self.train_df_data.index)
        if self.config.verbose:
            elapsed = time.perf_counter() - started_at
            print(f"prepare_training_dataset finished in {elapsed:.2f}s")
            print(f"Feature rows: {len(self.training_dataset)}, label rows: {len(self.training_label)}")
        return self.training_dataset

    def train_logistic_regression(self) -> Tuple[LogisticRegression, np.ndarray]:
        self._require_availability_target()
        if self.training_dataset is None:
            self.prepare_training_dataset()
        log_reg = LogisticRegression()
        log_reg.fit(self.training_dataset, self.training_label)

        log_reg_scores = cross_val_score(log_reg, self.training_dataset, self.training_label, scoring="accuracy", cv=5)
        print("Scores:", log_reg_scores)
        self.models["LogisticRegressionNotebook"] = log_reg
        return log_reg, log_reg_scores

    def train_xgboost_classifier(self) -> Tuple[xgb.XGBClassifier, np.ndarray]:
        self._require_availability_target()
        self._require_xgboost()
        if self.training_dataset is None:
            self.prepare_training_dataset()
        xgb_cl = xgb.XGBClassifier()
        xgb_cl.fit(self.training_dataset, self.training_label)
        xgb_cl_scores = cross_val_score(xgb_cl, self.training_dataset, self.training_label, scoring="accuracy", cv=5, n_jobs=-1)
        print("Scores:", xgb_cl_scores)
        self.models["XGBClassifierNotebook"] = xgb_cl
        return xgb_cl, xgb_cl_scores

    def train_wait_time_model(self) -> Tuple[RandomForestRegressor, Dict[str, float]]:
        self._require_duration_target()
        if self.training_dataset is None:
            self.prepare_training_dataset()
        train_target = self.get_train_target()
        wait_time_model = RandomForestRegressor(random_state=self.config.random_state, n_jobs=-1)
        wait_time_model.fit(self.training_dataset, train_target)

        if self.testing_data_final is None or self.testing_label is None:
            self.prepare_test_dataset()
        y_pred = wait_time_model.predict(self.testing_data_final)
        scores = {
            "mae": mean_absolute_error(self.testing_label, y_pred),
            "r2": r2_score(self.testing_label, y_pred),
        }
        print("Mean Absolute Error:", scores["mae"])
        print("R2 Score:", scores["r2"])
        self.models["WaitTimeRandomForest"] = wait_time_model
        return wait_time_model, scores

    def print_training_classification_report(self, model) -> np.ndarray:
        self._require_availability_target()
        if self.training_dataset is None:
            self.prepare_training_dataset()
        y_pred_probs = model.predict(self.training_dataset)
        y_pred = (y_pred_probs > 0.5).astype("int32")

        print(classification_report(self.training_label, y_pred))
        cm = confusion_matrix(self.training_label, y_pred)
        return cm

    def grid_search_models(self, saved: bool = False) -> Dict[str, Dict[str, object]]:
        self._require_availability_target()
        self._require_xgboost()
        if self.training_dataset is None:
            self.prepare_training_dataset()

        param_grid_lr = {
            "penalty": ["l2"],
            "C": [0.01, 0.1, 1, 10],
            "solver": ["liblinear", "saga"],
            "max_iter": [100, 500]
        }

        param_grid_dt = {
            "criterion": ["gini", "entropy"],
            "max_depth": [None, 5, 10, 20],
            "min_samples_split": [2, 5, 10]
        }

        param_grid_rf = {
            "n_estimators": [100, 200],
            "criterion": ["gini", "entropy"],
            "max_depth": [None, 10, 20],
            "min_samples_split": [2, 5]
        }

        param_grid_xgb = {
            "n_estimators": [100, 200],
            "max_depth": [3, 6, 10],
            "learning_rate": [0.01, 0.1],
            "subsample": [0.8, 1.0]
        }

        models = [
            ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=42), param_grid_lr),
            ("DecisionTree", DecisionTreeClassifier(random_state=42), param_grid_dt),
            ("RandomForest", RandomForestClassifier(random_state=42), param_grid_rf),
            ("XGBClassifier", xgb.XGBClassifier(eval_metric="logloss", random_state=42), param_grid_xgb),
        ]

        if not saved:
            for name, estimator, param_grid in models:
                grid = GridSearchCV(estimator, param_grid, scoring="accuracy", cv=5, n_jobs=-1, verbose=1)
                grid.fit(self.training_dataset, self.training_label)
                self.best_results[name] = {
                    "best_score": grid.best_score_,
                    "best_params": grid.best_params_,
                    "best_estimator": grid.best_estimator_
                }
                print(f"{name}: best_score={grid.best_score_:.4f}")
                print("best_params=", grid.best_params_)
                print()
        return self.best_results

    def save_best_models(self) -> None:
        if not self.best_results:
            raise RuntimeError("No grid search results available. Run grid_search_models first.")
        os.makedirs(self.config.model_dir, exist_ok=True)
        joblib.dump(self.best_results['XGBClassifier']['best_estimator'], self._model_path('best_xgb_model.pkl'))
        joblib.dump(self.best_results['XGBClassifier']['best_params'], self._model_path('best_xgb_params.pkl'))

        joblib.dump(self.best_results['RandomForest']['best_estimator'], self._model_path('best_rf_model.pkl'))
        joblib.dump(self.best_results['RandomForest']['best_params'], self._model_path('best_rf_params.pkl'))

        joblib.dump(self.best_results['DecisionTree']['best_estimator'], self._model_path('best_dt_model.pkl'))
        joblib.dump(self.best_results['DecisionTree']['best_params'], self._model_path('best_dt_params.pkl'))

        joblib.dump(self.best_results['LogisticRegression']['best_estimator'], self._model_path('best_lr_model.pkl'))
        joblib.dump(self.best_results['LogisticRegression']['best_params'], self._model_path('best_lr_params.pkl'))

    def load_best_models(self) -> Dict[str, object]:
        self.models["XGBClassifier"] = joblib.load(self._model_path('best_xgb_model.pkl'))
        self.models["XGBClassifierParams"] = joblib.load(self._model_path('best_xgb_params.pkl'))

        self.models["RandomForest"] = joblib.load(self._model_path('best_rf_model.pkl'))
        self.models["RandomForestParams"] = joblib.load(self._model_path('best_rf_params.pkl'))

        self.models["DecisionTree"] = joblib.load(self._model_path('best_dt_model.pkl'))
        self.models["DecisionTreeParams"] = joblib.load(self._model_path('best_dt_params.pkl'))

        self.models["LogisticRegression"] = joblib.load(self._model_path('best_lr_model.pkl'))
        self.models["LogisticRegressionParams"] = joblib.load(self._model_path('best_lr_params.pkl'))
        return self.models

    def build_voting_classifier(self) -> VotingClassifier:
        self._require_availability_target()
        required = ["XGBClassifier", "LogisticRegression", "RandomForest", "DecisionTree"]
        if not all(name in self.models for name in required):
            self.load_best_models()
        if self.training_dataset is None:
            self.prepare_training_dataset()

        xgb_best = self.models["XGBClassifier"]
        lr_best = self.models["LogisticRegression"]
        rf_best = self.models["RandomForest"]
        dc_best= self.models["DecisionTree"]

        self.voting_clf = VotingClassifier(
            estimators=[('lr', lr_best), ('rf', rf_best), ('dc', dc_best), ('xgb', xgb_best)],
            voting='hard'
        )
        self.voting_clf.fit(self.training_dataset, self.training_label)
        return self.voting_clf

    def prepare_test_dataset(self) -> Tuple[np.ndarray, pd.Series]:
        started_at = time.perf_counter()
        if self.test_df is None:
            self.split_dataset()
        if self.full_pipeline is None:
            self.prepare_training_dataset()
        drop_cols = [col for col in ['Availability','Total_Duration_Secs'] if col in self.test_df.columns]
        self.test_df_data = self.test_df.drop(drop_cols, axis = 1)
        if self.config.verbose:
            print(f"Preparing test data: {self.test_df_data.shape[0]} rows, {self.test_df_data.shape[1]} columns")
        transformed = self.full_pipeline.transform(self.test_df_data)
        self.testing_data_final = self._as_feature_frame(transformed, self.test_df_data.index)
        if self.target_column not in self.test_df.columns:
            raise KeyError(f"Target column '{self.target_column}' is missing from the test data.")
        self.testing_label = self.test_df[self.target_column].copy()
        if self.config.verbose:
            elapsed = time.perf_counter() - started_at
            print(f"prepare_test_dataset finished in {elapsed:.2f}s")
            print(f"Feature rows: {len(self.testing_data_final)}, label rows: {len(self.testing_label)}")
        return self.testing_data_final, self.testing_label

    def evaluate_classifiers(self, classifiers: Optional[Iterable[object]] = None) -> None:
        self._require_availability_target()
        if self.testing_data_final is None or self.testing_label is None:
            self.prepare_test_dataset()
        if classifiers is None:
            required = ["LogisticRegression", "RandomForest", "DecisionTree", "XGBClassifier"]
            if not all(name in self.models for name in required):
                self.load_best_models()
            if self.voting_clf is None:
                self.build_voting_classifier()
            classifiers = (
                self.models["LogisticRegression"],
                self.models["RandomForest"],
                self.models["DecisionTree"],
                self.models["XGBClassifier"],
                self.voting_clf,
            )
        for clf in classifiers:
            y_pred = clf.predict(self.testing_data_final)
            print(clf.__class__.__name__, accuracy_score(self.testing_label, y_pred))

    def print_test_classification_report(self, model=None) -> np.ndarray:
        self._require_availability_target()
        if self.testing_data_final is None or self.testing_label is None:
            self.prepare_test_dataset()
        if model is None:
            if "XGBClassifier" not in self.models:
                self.load_best_models()
            model = self.models["XGBClassifier"]
        y_pred_probs = model.predict(self.testing_data_final)
        y_pred = (y_pred_probs > 0.5).astype("int32")

        print(classification_report(self.testing_label, y_pred))
        cm = confusion_matrix(self.testing_label, y_pred)
        print(cm)
        return cm

    def create_training_sequences(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.training_dataset is None:
            self.prepare_training_dataset()
        features = self.training_dataset.columns
        train_target = self.get_train_target()
        temp_df = pd.concat([self.training_dataset, train_target], axis=1)
        self.X_final, self.y_final = create_grouped_sequences(temp_df, features, self.target_column, time_steps=self.config.time_steps)
        return self.X_final, self.y_final

    def create_test_sequences(self) -> Tuple[np.ndarray, np.ndarray]:
        if self.testing_dataset is None or self.testing_label is None:
            self.prepare_test_dataset()
        features = self.training_dataset.columns
        temp_df = pd.concat([self.testing_dataset, self.testing_label], axis=1)

        self.X_test_seq, self.y_test_seq = create_grouped_sequences(
            df=temp_df, 
            feature_cols=features, 
            target_col=self.target_column, 
            time_steps=self.config.time_steps
        )
        return self.X_test_seq, self.y_test_seq

    def build_lstm_model(self):
        if self.X_final is None or self.y_final is None:
            self.create_training_sequences()

        from tensorflow.keras.layers import Bidirectional, LSTM, Dense, Dropout, BatchNormalization
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.regularizers import l2

        output_activation = 'sigmoid' if self.available else 'linear'
        loss = 'binary_crossentropy' if self.available else 'mse'
        metrics = ['accuracy'] if self.available else ['mae']

        self.lstm_model = Sequential([
            # Layer 1: Bidirectional helps catch patterns from both directions
            Bidirectional(LSTM(units=128, return_sequences=True, kernel_regularizer=l2(0.01)), 
                          input_shape=(self.X_final.shape[1], self.X_final.shape[2])),
            BatchNormalization(),
            Dropout(0.3),
            
            # Layer 2: Increased units to handle the new weather/time features
            LSTM(units=64, return_sequences=False),
            BatchNormalization(),
            Dropout(0.3),
            
            # Layer 3: Wider Dense layer to interpret the LSTM states
            Dense(64, activation='relu'),
            Dense(1, activation=output_activation)
        ])

        self.lstm_model.compile(optimizer='adam', loss=loss, metrics=metrics)
        return self.lstm_model

    def train_lstm(self, epochs: int = 15, batch_size: int = 32, verbose: int = 1):
        if self.lstm_model is None:
            self.build_lstm_model()
        if self.X_test_seq is None or self.y_test_seq is None:
            self.create_test_sequences()
        history = self.lstm_model.fit(
            self.X_final, self.y_final, 
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(self.X_test_seq, self.y_test_seq),
            verbose=verbose
        )
        return history

    def save_lstm_model(self) -> None:
        if self.lstm_model is None:
            raise RuntimeError("No LSTM model available. Run build_lstm_model or train_lstm first.")
        os.makedirs(self.config.model_dir, exist_ok=True)
        joblib.dump(self.lstm_model, self._model_path('lstm.pkl'))

    def evaluate_lstm_on_training(self) -> float:
        if self.X_final is None or self.y_final is None:
            self.create_training_sequences()
        model = joblib.load(self._model_path('lstm.pkl'))
        y_pred_probs = model.predict(self.X_final)

        if self.available:
            y_pred = (y_pred_probs > 0.5).astype("int32")
            print(classification_report(self.y_final, y_pred))
            return accuracy_score(self.y_final, y_pred)
        return mean_absolute_error(self.y_final, y_pred_probs)

    def run_classical_workflow(self, do_grid_search: bool = False, save_models: bool = False) -> None:
        self.load_data()
        self.build_dataset()
        self.split_dataset()
        self.prepare_training_dataset()
        if do_grid_search:
            self.grid_search_models(saved=False)
            if save_models:
                self.save_best_models()
        self.load_best_models()
        self.build_voting_classifier()
        self.prepare_test_dataset()
        self.evaluate_classifiers()
        self.print_test_classification_report()

    def run_lstm_workflow(self, epochs: int = 15, batch_size: int = 32) -> None:
        self.load_data()
        self.build_dataset()
        self.split_dataset()
        self.prepare_training_dataset()
        self.prepare_test_dataset()
        self.create_training_sequences()
        self.create_test_sequences()
        self.build_lstm_model()
        self.train_lstm(epochs=epochs, batch_size=batch_size)
        self.save_lstm_model()
        print("Training accuracy:", self.evaluate_lstm_on_training())

    def _model_path(self, filename: str) -> str:
        return os.path.join(self.config.model_dir, filename)

    @staticmethod
    def _as_feature_frame(transformed, index) -> pd.DataFrame:
        if isinstance(transformed, pd.DataFrame):
            transformed = transformed.copy()
            transformed.index = index
            return transformed
        return pd.DataFrame(transformed, index=index)

    def _require_availability_target(self) -> None:
        if self.target_column != "Availability":
            raise ValueError("This method is for the availability classification dataset. Run build_dataset(available=True).")

    def _require_duration_target(self) -> None:
        if self.target_column != "Total_Duration_Secs":
            raise ValueError("This method is for the wait-time duration dataset. Run build_dataset(available=False).")

    @staticmethod
    def _require_xgboost() -> None:
        if xgb is None:
            raise ModuleNotFoundError("xgboost is required for this part of the workflow.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OOP time-series forecasting pipeline.")
    parser.add_argument("--data-path", default=TimeSeriesForecastConfig.data_path)
    parser.add_argument("--model-dir", default=TimeSeriesForecastConfig.model_dir)
    parser.add_argument("--run", choices=("none", "classical", "lstm"), default="none")
    parser.add_argument("--grid-search", action="store_true")
    parser.add_argument("--save-models", action="store_true")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = TimeSeriesForecastConfig(data_path=args.data_path, model_dir=args.model_dir)
    pipeline = TimeSeriesForecastPipeline(config)

    if args.run == "classical":
        pipeline.run_classical_workflow(do_grid_search=args.grid_search, save_models=args.save_models)
    elif args.run == "lstm":
        pipeline.run_lstm_workflow(epochs=args.epochs, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
