"""Gemini charger assistant with tools that read the station database and run the algorithm."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from google import genai
from google.genai import errors, types

from . import config
from .algorithm import TAIPEI_TZ, estimate_range, recommend
from .data import store
from .geo import CITIES, city_label, resolve_city
from .routing import road_distances

log = logging.getLogger(__name__)

RETRYABLE = {429, 500, 502, 503, 504, 404}


class AssistantUnavailable(RuntimeError):
    """Gemini is not configured or every model failed."""


@dataclass
class ChatContext:
    lat: float
    lng: float
    battery_pct: float
    lang: str = "en"
    capacity_kwh: float = config.DEFAULT_CAPACITY_KWH
    wh_per_km: float = config.DEFAULT_WH_PER_KM
    dest_id: str | None = None
    voice: bool = False  # the reply will be read aloud to someone driving
    seen: dict[str, dict] = field(default_factory=dict)  # every station a tool returned
    last_list: list[dict] = field(default_factory=list)  # stations from the latest tool call

    def remember(self, items: list[dict]) -> list[dict]:
        for item in items:
            self.seen[item["id"]] = item
        self.last_list = items
        return items


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if not config.GEMINI_API_KEY:
        raise AssistantUnavailable("GEMINI_API_KEY is not set")
    if _client is None:
        # v1beta: function calling together with thinking settings is rejected on v1.
        _client = genai.Client(api_key=config.GEMINI_API_KEY, http_options={"api_version": "v1beta"})
    return _client


# ── Tools ────────────────────────────────────────────────────────────────────


def _for_llm(row: dict) -> dict:
    """Hide the placeholder wait score so Gemini can't present it as a real prediction."""
    if not row.get("wait", {}).get("placeholder"):
        return row
    row = dict(row)
    row["wait"] = "not predicted yet (model unfinished)"
    row["normalized"] = {k: v for k, v in row.get("normalized", {}).items() if k != "wait"}
    row["contributions"] = {k: v for k, v in row.get("contributions", {}).items() if k != "wait"}
    return row


def _hit(item: dict) -> dict:
    """The fields the app needs to draw a station card."""
    return {k: item.get(k) for k in ("id", "name", "lat", "lng", "city", "source", "km")}


def make_tools(ctx: ChatContext) -> list:
    db = store()

    def find_stations(query: str = "", city: str = "", limit: int = 5) -> dict:
        """Search Taiwan EV charging stations by name keyword and/or city.

        Use for questions like "stations in Kaohsiung" or "Taipei Main Station charger".
        Results are sorted by straight-line distance from the user.

        Args:
            query: Part of the station name in Chinese or English, e.g. "車站", "IKEA". Empty to list a whole city.
            city: City or county name in English or Chinese, e.g. "Kaohsiung", "台中". Empty for all of Taiwan.
            limit: How many stations to return (1-10).
        """
        c = resolve_city(city) if city else None
        if city and not c:
            return {"error": f"Unknown city '{city}'.", "known_cities": [x.en for x in CITIES]}
        if query.strip():
            matches = db.search(query, city=c)
        elif c:
            matches = [s for s in db.stations if s.city == c.code]
        else:
            return {"error": "Give a name keyword or a city."}
        items = sorted((s.brief(ctx.lat, ctx.lng, ctx.lang) for s in matches), key=lambda x: x["km"])
        limit = max(1, min(10, int(limit)))
        return {
            "total_matches": len(items),
            "city": c.en if c else None,
            "stations": ctx.remember(items[:limit]),
        }

    def nearby_stations(radius_km: float = 10, limit: int = 5) -> dict:
        """List charging stations closest to the user's current location.

        Args:
            radius_km: Search radius in kilometres (1-50).
            limit: How many stations to return (1-10).
        """
        radius_km = max(1.0, min(50.0, float(radius_km)))
        rows = db.nearest(ctx.lat, ctx.lng, radius_km=radius_km)
        items = [s.brief(ctx.lat, ctx.lng, ctx.lang) for s, _ in rows]
        out = {"radius_km": radius_km, "total_in_radius": len(items), "stations": ctx.remember(items[: max(1, min(10, int(limit)))])}
        if not items:
            nearest = db.nearest(ctx.lat, ctx.lng, limit=1)
            if nearest:
                out["closest_outside_radius"] = ctx.remember([nearest[0][0].brief(ctx.lat, ctx.lng, ctx.lang)])[0]
        return out

    def recommend_stations(battery_pct: float = -1, city: str = "", limit: int = 5) -> dict:
        """Run the project's recommendation algorithm and return the best chargers to go to now.

        It keeps only stations the car can reach on its battery, then ranks them by a
        weighted score of road distance, predicted waiting time and charging price.
        Use this whenever the user asks what to choose, what is best, or for a recommendation.

        Args:
            battery_pct: Battery level 0-100. Use -1 for the user's current level.
            city: Optional city or county to restrict the search, in English or Chinese.
            limit: How many ranked stations to return (1-10).
        """
        c = resolve_city(city) if city else None
        if city and not c:
            return {"error": f"Unknown city '{city}'."}
        pct = ctx.battery_pct if battery_pct is None or battery_pct < 0 else battery_pct
        rec = recommend(
            ctx.lat,
            ctx.lng,
            pct,
            capacity_kwh=ctx.capacity_kwh,
            wh_per_km=ctx.wh_per_km,
            city=c,
            limit=max(1, min(10, int(limit))),
            lang=ctx.lang,
        )
        ctx.remember(rec["results"])
        rec.pop("all_results", None)
        rec["results"] = [_for_llm(r) for r in rec["results"]]
        rec["notes"] = [
            "waiting time is a placeholder (model not finished): do not claim a charger is free or busy",
            f"charging prices are known for {rec.get('prices_known', 0)} of the scored stations; unknown prices use the median",
        ]
        return rec

    def station_details(station_id: str) -> dict:
        """Full details for one station: address, operator, plug type, charging and parking prices, and road distance and drive time from the user.

        Args:
            station_id: The station "id" returned by another tool.
        """
        d = db.details(station_id)
        if not d:
            return {"error": f"No station with id '{station_id}'."}
        metres, secs, source = road_distances((ctx.lat, ctx.lng), [(d["lat"], d["lng"])])
        d["city_name"] = city_label(d["city"], ctx.lang)
        d["road_distance_km"] = round(metres[0] / 1000, 1)
        d["drive_minutes"] = round(secs[0] / 60) if secs[0] else None
        d["distance_source"] = source
        d["reachable_on_current_battery"] = metres[0] / 1000 <= estimate_range(ctx.battery_pct, ctx.capacity_kwh, ctx.wh_per_km)["max_range_km"]
        s = db.get(station_id)
        ctx.remember([s.brief(ctx.lat, ctx.lng, ctx.lang)])
        return d

    def battery_range(battery_pct: float = -1) -> dict:
        """Estimate how far the car can drive on a battery level, using the project's range formula.

        Args:
            battery_pct: Battery level 0-100. Use -1 for the user's current level.
        """
        pct = ctx.battery_pct if battery_pct is None or battery_pct < 0 else battery_pct
        return estimate_range(pct, ctx.capacity_kwh, ctx.wh_per_km)

    def city_overview() -> dict:
        """Number of charging stations in each Taiwan city or county, and how many have price data."""
        counts = db.city_counts()
        return {
            "cities": [
                {"city": c.en, "zh": c.zh, **counts.get(c.code, {"stations": 0, "with_price": 0})}
                for c in CITIES
            ],
            "total_stations": len(db.stations),
        }

    return [find_stations, nearby_stations, recommend_stations, station_details, battery_range, city_overview]


# ── Prompts ──────────────────────────────────────────────────────────────────


def _system_prompt(ctx: ChatContext) -> str:
    now = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M (%A)")
    lang = "Traditional Chinese (台灣用語)" if ctx.lang == "zh" else "English"
    dest = store().get(ctx.dest_id) if ctx.dest_id else None
    dest_line = (
        f"The user has selected '{dest.name or dest.id}' (id {dest.id}) as their destination."
        if dest
        else "The user has not selected a destination."
    )
    voice_rules = (
        """
Voice mode (this answer is spoken aloud to someone who is driving):
- The user's message is a speech transcript and may contain recognition mistakes; read it charitably.
- Answer in 1 to 3 short spoken sentences. Mention at most 3 stations, best first.
- Round numbers the way people say them ("about 2.5 kilometres", "about 8 minutes"). No lists, symbols, ids or coordinates.
- Never ask them to read or tap the screen while driving; say the cards are there for when they have stopped."""
        if ctx.voice
        else ""
    )
    return f"""You are the charger assistant inside MapExplore, an EV charging app for Taiwan.

User context:
- Location: {ctx.lat:.5f}, {ctx.lng:.5f}. Local time: {now} (Taiwan).
- Battery: {ctx.battery_pct:.0f}% of a {ctx.capacity_kwh:.0f} kWh pack, using about {ctx.wh_per_km:.0f} Wh/km.
- {dest_line}

Rules:
- Reply in {lang} unless the user clearly writes in another language.
- Get every station fact (names, counts, distances, prices) from the tools. Never invent stations or numbers.
- For "which one / best / recommend" questions, call recommend_stations and explain the top choice using its score breakdown.
- When the user says "this one" or "here", they mean the selected destination.
- Waiting time comes from a placeholder, not a real prediction. Never say a charger is free, busy, or has a queue.
- Price data exists for few stations (mostly Taipei). If a price is missing, say it is unknown.
- "km" in results is straight-line distance; distance_m and road_distance_km are by road.
- Write short, plain answers for a phone screen: at most 4 sentences or a short list of up to 5 stations. No markdown headings, tables, or bold.
- Use station names exactly as the tools return them. The app shows tappable cards for the stations you mention.
- If a question is unrelated to EV charging or driving in Taiwan, answer briefly and steer back.{voice_rules}"""


def _generate(
    contents, cfg: types.GenerateContentConfig, thinking: str | None = None
) -> tuple[types.GenerateContentResponse, str]:
    client = _get_client()
    last: Exception | None = None
    for model in config.GEMINI_MODELS:
        model_cfg = cfg
        if thinking and model.startswith("gemini-3"):  # thinking levels are a Gemini 3 feature
            model_cfg = cfg.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level=thinking)})
        try:
            return client.models.generate_content(model=model, contents=contents, config=model_cfg), model
        except errors.APIError as exc:
            last = exc
            if getattr(exc, "code", None) in RETRYABLE:
                log.warning("Gemini model %s failed (%s), trying next", model, exc.code)
                continue
            raise
    raise AssistantUnavailable(f"All Gemini models failed: {last}")


def _tools_used(resp: types.GenerateContentResponse) -> list[str]:
    names = []
    for content in resp.automatic_function_calling_history or []:
        for part in content.parts or []:
            if part.function_call:
                names.append(part.function_call.name)
    return names


def _pick_cards(reply: str, ctx: ChatContext) -> list[dict]:
    mentioned = [item for item in ctx.seen.values() if item.get("name") and item["name"] in reply]
    picks = mentioned or ctx.last_list
    return [_hit(item) for item in picks[:5]]


def chat(message: str, history: list[dict], ctx: ChatContext) -> dict:
    contents = []
    for turn in history[-12:]:
        text = str(turn.get("text") or "").strip()
        if not text:
            continue
        role = "model" if turn.get("role") in ("model", "bot", "assistant") else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text[:2000])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message[:2000])]))

    cfg = types.GenerateContentConfig(
        system_instruction=_system_prompt(ctx),
        tools=make_tools(ctx),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=config.GEMINI_MAX_TOOL_CALLS
        ),
        temperature=0.3,
    )
    resp, model = _generate(contents, cfg, thinking=config.GEMINI_VOICE_THINKING if ctx.voice else None)
    reply = (resp.text or "").strip()
    if not reply:
        reply = (
            "抱歉，我這次沒有整理出答案，請換個方式再問一次。"
            if ctx.lang == "zh"
            else "Sorry, I couldn't put an answer together. Please try asking another way."
        )
    return {"reply": reply, "stations": _pick_cards(reply, ctx), "model": model, "tools_used": _tools_used(resp)}


# ── Explanation for one recommended station ─────────────────────────────────


def _rules_explanation(row: dict, rec: dict, lang: str) -> str:
    km = row["distance_m"] / 1000
    price = row["cost"]["ntd_per_kwh"]
    if lang == "zh":
        parts = [f"{row['name']} 在 {rec['considered']} 個候選站中排第 {row['rank']}，總分 {row['total_score']:.2f}。"]
        parts.append(f"車程約 {km:.1f} 公里" + (f"、約 {round(row['duration_s'] / 60)} 分鐘" if row.get("duration_s") else "") + "。")
        parts.append(f"充電價格約每度 {price:g} 元。" if price is not None else "這站沒有價格資料，以其他站的中位數計算。")
        parts.append("等候時間目前是預設值，還不是模型預測。")
        return "".join(parts)
    parts = [f"{row['name']} ranks #{row['rank']} of {rec['considered']} candidates with a score of {row['total_score']:.2f}."]
    parts.append(f"It's about {km:.1f} km by road" + (f", roughly {round(row['duration_s'] / 60)} min" if row.get("duration_s") else "") + ".")
    parts.append(f"Charging costs about NT${price:g}/kWh." if price is not None else "There's no price data for it, so the median price was used.")
    parts.append("Waiting time is a placeholder, not a model prediction yet.")
    return " ".join(parts)


def explain(station_id: str, ctx: ChatContext) -> dict | None:
    rec = recommend(
        ctx.lat,
        ctx.lng,
        ctx.battery_pct,
        capacity_kwh=ctx.capacity_kwh,
        wh_per_km=ctx.wh_per_km,
        include_ids=(station_id,),
        lang=ctx.lang,
    )
    row = next((r for r in rec.get("all_results", []) if r["id"] == station_id), None)
    if row is None:
        return None
    alternatives = [
        {k: r[k] for k in ("name", "rank", "total_score", "distance_m", "cost")}
        for r in rec["all_results"]
        if r["id"] != station_id
    ][:3]
    payload = {
        "station": {k: v for k, v in _for_llm(row).items() if k in ("name", "city_name", "rank", "total_score", "distance_m", "duration_s", "reachable", "cost", "normalized", "contributions", "reasons", "wait")},
        "candidates_scored": rec["considered"],
        "range": rec["range"],
        "weights": rec["weights"],
        "top_alternatives": alternatives,
        "notes": ["waiting time is a placeholder; do not claim availability", "distance_m is road distance in metres"],
    }
    lang = "Traditional Chinese (台灣用語)" if ctx.lang == "zh" else "English"
    prompt = (
        f"Explain to a driver, in {lang}, why this charging station got its rank. "
        "Use 2-3 short plain sentences, no markdown. Mention distance and price (or that price is unknown), "
        "compare briefly with the best alternative, and if it is not reachable on the current battery say so.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    score = {k: row[k] for k in ("rank", "total_score", "normalized", "contributions", "distance_m", "duration_s", "cost", "wait", "reachable")}
    try:
        resp, model = _generate(prompt, types.GenerateContentConfig(temperature=0.3))
        text = (resp.text or "").strip()
        if text:
            return {"explanation": text, "source": "gemini", "model": model, "score": score}
    except (AssistantUnavailable, errors.APIError) as exc:
        log.warning("Explain fell back to rules: %s", exc)
    return {"explanation": _rules_explanation(row, rec, ctx.lang), "source": "rules", "model": None, "score": score}
