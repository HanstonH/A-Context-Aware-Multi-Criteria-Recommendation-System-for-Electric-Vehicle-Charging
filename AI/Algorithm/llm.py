import json
import os
from typing import Any, Dict, Union

import pandas as pd
from google import genai
from google.genai import types


API_KEY = os.getenv("GEMINI_API_KEY", "")


def format_llm_payload(station_data: Union[Dict[str, Any], list, pd.DataFrame]) -> Dict[str, Any]:
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


def generate_ev_explanation(station_data: Union[Dict[str, Any], list, pd.DataFrame]) -> str:
    """Generate a short driver-facing explanation from ranked station context."""
    client = genai.Client()

    system_instruction = (
        "You are a helpful EV charging assistant. Your goal is to look at the data "
        "of a highly recommended EV station and explain to the driver why they should "
        "pick it compared to the alternatives. Use the nearby_pois list, scores, "
        "distance_metres, waiting_time_seconds, and cost_per_kwh. Focus on clear "
        "trade-offs (distance, price, nearby places, waiting time). Treat the user as "
        "if they only know basic words; be concise. Lead with the single strongest reason."
    )

    payload = format_llm_payload(station_data)
    user_prompt = (
        "Recommendation context (JSON):\n"
        f"{json.dumps(payload, indent=2, default=str)}\n\n"
        "Explain why the driver should choose recommended_station over the alternatives."
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3,
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=user_prompt,
        config=config,
    )

    return response.text
