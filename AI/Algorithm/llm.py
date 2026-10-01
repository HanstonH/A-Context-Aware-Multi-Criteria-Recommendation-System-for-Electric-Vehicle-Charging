"""
Reflection-based text justification engine for EV charging recommendations.

Pipeline:
  1. Draft V1   — initial 2-sentence justification
  2. Critique   — self-evaluation for hallucinations, tone, trade-off accuracy
  3. Final V2   — revised 2-sentence justification incorporating the critique

Gemini calls use ``MODEL_FALLBACK_CHAIN`` (3.5 Flash → 2.5 Flash → 2.5 Pro →
2 Flash → 2 Flash Lite) when a model cannot be reached.

Compatible with ``logic.total_score(..., include_llm_context=True)`` payloads.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Tried in order when a model is unavailable, rate-limited, or returns empty text.
MODEL_FALLBACK_CHAIN: List[str] = [
    "gemini-3.5-flash",       # Gemini 3.5 Flash
    "gemini-2.5-flash",       # Gemini 2.5 Flash
    "gemini-2.5-pro",         # Gemini 2.5 Pro
    "gemini-2.0-flash",       # Gemini 2 Flash
    "gemini-2.0-flash-lite",  # Gemini 2 Flash Lite
]

MODEL_ID = MODEL_FALLBACK_CHAIN[0]

_logger = logging.getLogger(__name__)

StationInput = Union[Dict[str, Any], list, pd.DataFrame]


@dataclass
class ReflectionResult:
    """Outputs from the full reflection pipeline."""

    station_data: Dict[str, Any]
    draft_v1: str
    critique: str
    final_v2: str


# ---------------------------------------------------------------------------
# Input normalization
# ---------------------------------------------------------------------------


def format_llm_payload(station_data: StationInput) -> Dict[str, Any]:
    """
    Normalize inputs from ``total_score(..., include_llm_context=True)`` into a
    single prompt-friendly structure.
    """
    if isinstance(station_data, pd.DataFrame):
        if "llm_context" in station_data.columns:
            contexts = station_data["llm_context"].tolist()
        else:
            contexts = station_data.to_dict(orient="records")
        return {
            "recommended_station": contexts[0] if contexts else None,
            "alternatives": contexts[1:5],
        }

    if isinstance(station_data, list):
        return {
            "recommended_station": station_data[0] if station_data else None,
            "alternatives": station_data[1:5],
        }

    if isinstance(station_data, dict) and "recommended" in station_data:
        return {
            "recommended_station": station_data.get("recommended"),
            "alternatives": station_data.get("alternatives") or [],
        }

    if isinstance(station_data, dict) and "llm_context" in station_data:
        return {"recommended_station": station_data["llm_context"], "alternatives": []}

    return {"recommended_station": station_data, "alternatives": []}


def _payload_to_json(payload: Dict[str, Any]) -> str:
    """Stable JSON string for prompts (handles numpy/pandas types)."""
    return json.dumps(payload, indent=2, default=str)


# ---------------------------------------------------------------------------
# Gemini client helpers
# ---------------------------------------------------------------------------


def _get_client() -> genai.Client:
    """Build a Gemini client (reads ``GEMINI_API_KEY`` from the environment)."""
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Export it before running the reflection pipeline."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def _call_gemini(
    *,
    system_instruction: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> str:
    """
    Single generate_content call with model fallback.

    Tries each model in ``MODEL_FALLBACK_CHAIN`` until one returns non-empty text.
  """
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )

    failures: List[str] = []
    for model_id in MODEL_FALLBACK_CHAIN:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=user_prompt,
                config=config,
            )
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("empty response")
            if model_id != MODEL_FALLBACK_CHAIN[0]:
                _logger.warning(
                    "Gemini fallback: using %s after earlier models failed.",
                    model_id,
                )
            return text
        except Exception as exc:
            failures.append(f"{model_id}: {exc}")
            _logger.warning("Gemini model %s unavailable: %s", model_id, exc)

    raise RuntimeError(
        "All Gemini models failed. Attempts:\n  - " + "\n  - ".join(failures)
    )


# ---------------------------------------------------------------------------
# Step 1 — Initial generation (Draft V1)
# ---------------------------------------------------------------------------

_DRAFT_V1_SYSTEM = (
    "You are a helpful EV charging assistant. The driver is choosing among "
    "several stations; you are explaining only the top-ranked station. "
    "Use ONLY facts present in the provided JSON. Do not invent amenities, "
    "prices, wait times, or place names. Write exactly two short sentences."
)


def generate_draft_v1(payload: Dict[str, Any]) -> str:
    """
    Step 1: Produce a concise 2-sentence draft justification (V1).

    Parameters
    ----------
    payload : dict
        Output of ``format_llm_payload`` (recommended_station + alternatives).
    """
    user_prompt = (
        "Station recommendation data (JSON):\n"
        f"{_payload_to_json(payload)}\n\n"
        "The recommended_station has the highest multi-criteria score "
        "(distance, cost, availability). Nearby POIs are listed for context "
        "only and do not affect the score. "
        "Write concise sentences explaining why the driver should "
        "pick recommended_station. Mention the strongest trade-offs supported "
        "by the data only. Optionally mention up to 3 nearby POIs the driver "
        "could visit while charging. "
    )
    return _call_gemini(
        system_instruction=_DRAFT_V1_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.35,
    )


# ---------------------------------------------------------------------------
# Step 2 — Reflection / critique
# ---------------------------------------------------------------------------

_CRITIQUE_SYSTEM = (
    "You are a strict quality reviewer for EV charging copy. "
    "Compare the draft text against the JSON data only. "
    "Flag any hallucination (claims not supported by the data), tone issues, "
    "or missed high-scoring trade-offs. Be direct and specific."
)


def generate_critique(payload: Dict[str, Any], draft_v1: str) -> str:
    """
    Step 2: Critically evaluate Draft V1 against the original station data.

    Checks for data hallucinations, helpful tone, and accurate trade-offs.
    """
    user_prompt = (
        "Original station data (JSON):\n"
        f"{_payload_to_json(payload)}\n\n"
        "Draft V1 explanation:\n"
        f"{draft_v1}\n\n"
        "Evaluate Draft V1. Structure your answer as:\n"
        "1. Hallucinations: (list any invented facts, or write 'None')\n"
        "2. Tone: (helpful / unclear / too technical — brief note)\n"
        "3. Trade-offs: (does it reflect the best-scoring factors in the data?)\n"
        "4. Critique: (one short paragraph with concrete fix instructions)"
    )
    return _call_gemini(
        system_instruction=_CRITIQUE_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.2,
    )


# ---------------------------------------------------------------------------
# Step 3 — Revision (Final V2)
# ---------------------------------------------------------------------------

_REVISION_SYSTEM = (
    "You are a helpful EV charging assistant. Rewrite the explanation using "
    "ONLY facts from the JSON and the reviewer critique. "
    "Fix every issue raised. Do not add new facts. "
    "Output exactly two clear, compelling sentences for the driver."
)


def generate_final_v2(
    payload: Dict[str, Any],
    draft_v1: str,
    critique: str,
) -> str:
    """
    Step 3: Rewrite into a flawless 2-sentence final justification (V2).
    """
    user_prompt = (
        "Original station data (JSON):\n"
        f"{_payload_to_json(payload)}\n\n"
        "Draft V1:\n"
        f"{draft_v1}\n\n"
        "Reviewer critique:\n"
        f"{critique}\n\n"
        "Write the final V2 explanation: exactly two sentences, accurate, "
        "friendly, and focused on why this station is the best choice."
    )
    return _call_gemini(
        system_instruction=_REVISION_SYSTEM,
        user_prompt=user_prompt,
        temperature=0.25,
    )


# ---------------------------------------------------------------------------
# Orchestration & reporting
# ---------------------------------------------------------------------------


def run_reflection_pipeline(station_data: StationInput) -> ReflectionResult:
    """
    Run the full reflection loop: Draft V1 → Critique → Final V2.

  Returns
    -------
    ReflectionResult
        Contains normalized station data and all three text stages.
    """
    payload = format_llm_payload(station_data)
    if not payload.get("recommended_station"):
        raise ValueError("No recommended station found in the input data.")

    draft_v1 = generate_draft_v1(payload)
    critique = generate_critique(payload, draft_v1)
    final_v2 = generate_final_v2(payload, draft_v1, critique)

    return ReflectionResult(
        station_data=payload,
        draft_v1=draft_v1,
        critique=critique,
        final_v2=final_v2,
    )


def print_reflection_report(result: ReflectionResult) -> None:
    """Print the four pipeline outputs for inspection / demos."""
    separator = "=" * 72
    print(separator)
    print("ORIGINAL STATION DATA")
    print(separator)
    # print(_payload_to_json(result.station_data))
    print()
    print(separator)
    print("DRAFT V1 EXPLANATION")
    print(separator)
    print(result.draft_v1)
    print()
    print(separator)
    print("LLM SELF-CRITIQUE")
    print(separator)
    print(result.critique)
    print()
    print(separator)
    print("FINAL V2 EXPLANATION")
    print(separator)
    print(result.final_v2)
    print(separator)


def generate_ev_explanation(station_data: StationInput) -> str:
    """
    Backward-compatible entry point used by ``logic.main()``.

    Runs the reflection pipeline and returns only the final V2 text.
    """
    return run_reflection_pipeline(station_data).final_v2


# ---------------------------------------------------------------------------
# CLI demo (``python llm.py``)
# ---------------------------------------------------------------------------

def _demo_station_payload() -> Dict[str, Any]:
    """Minimal example matching ``logic.build_llm_station_record`` shape."""
    return {
        "recommended": {
            "rank": 1,
            "station_name": "Palo Alto City Hall",
            "coordinates": {"latitude": 37.445, "longitude": -122.163},
            "distance_metres": 420.0,
            "waiting_time_seconds": 0.0,
            "cost_per_kwh": 0.0,
            "poi_count": 2,
            "nearby_pois": [
                {
                    "name": "Blue Bottle Coffee",
                    "rating": 4.6,
                    "review_count": 312,
                    "distance_metres": 95,
                    "open_now": True,
                },
                {
                    "name": "Town & Country Village",
                    "rating": 4.4,
                    "review_count": 890,
                    "distance_metres": 280,
                    "open_now": True,
                },
            ],
            "scores": {
                "total_score": 0.91,
                "normalized": {
                    "distance": 0.95,
                    "waiting": 1.0,
                    "cost": 1.0,
                },
                "weighted_contributions": {
                    "distance": 0.32,
                    "waiting": 0.33,
                    "cost": 0.33,
                },
            },
            "explanation": {
                "summary": "Total score 0.980 (distance 0.95, wait 1.00, cost 1.00).",
                "reasons": [
                    "Strong travel distance compared to other options.",
                    "Strong queue wait compared to other options.",
                ],
            },
        },
        "alternatives": [
            {
                "rank": 2,
                "station_name": "Stanford Shopping Center",
                "distance_metres": 2100.0,
                "waiting_time_seconds": 480.0,
                "cost_per_kwh": 0.42,
                "scores": {"total_score": 0.54},
            }
        ],
    }


if __name__ == "__main__":
    demo_input: Optional[StationInput] = None
    # Extend here to load from argv / JSON file if needed.
    payload = demo_input if demo_input is not None else _demo_station_payload()
    report = run_reflection_pipeline(payload)
    print_reflection_report(report)
