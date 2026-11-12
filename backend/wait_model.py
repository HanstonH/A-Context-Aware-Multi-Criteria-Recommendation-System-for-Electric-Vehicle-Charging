"""Waiting-time prediction — PLACEHOLDER until Model A/B are finished.

The real version should follow Calculation_Model.predict_waiting_time in
AI/Algorithm/logic.py: Model A predicts whether the charger is free when the
driver arrives; if not, Model B predicts how long the current session lasts.

To plug the real model in, replace ``predict_wait_seconds`` and set
``placeholder`` to False. Nothing else in the backend needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from . import config
from .data import Station


@dataclass
class WaitPrediction:
    seconds: float
    placeholder: bool
    available: bool | None  # None = unknown


def predict_wait_seconds(
    station: Station, *, arrival: datetime, road_seconds: float | None
) -> WaitPrediction:
    # Same value for every station, so it cannot change the ranking.
    return WaitPrediction(
        seconds=config.WAIT_PLACEHOLDER_MIN * 60,
        placeholder=True,
        available=None,
    )
