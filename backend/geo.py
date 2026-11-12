"""Distances and Taiwan city names (kept in sync with app/chatbot.ts)."""

from __future__ import annotations

import math
from dataclasses import dataclass


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    s = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(s), math.sqrt(1 - s))


@dataclass(frozen=True)
class City:
    code: str  # value of stations.city in the database
    zh: str
    en: str
    lat: float
    lng: float
    keys: tuple[str, ...]


CITIES: tuple[City, ...] = (
    City("Keelung", "基隆", "Keelung", 25.1276, 121.7392, ("基隆", "keelung")),
    City("Taipei", "台北", "Taipei", 25.033, 121.5654, ("台北", "臺北", "taipei")),
    City("NewTaipei", "新北", "New Taipei", 25.017, 121.463, ("新北", "new taipei", "newtaipei")),
    City("Taoyuan", "桃園", "Taoyuan", 24.993, 121.301, ("桃園", "taoyuan")),
    City("HsinchuCounty", "新竹縣", "Hsinchu County", 24.827, 121.012, ("新竹縣", "hsinchu county", "hsinchucounty")),
    City("Hsinchu", "新竹", "Hsinchu", 24.8138, 120.9675, ("新竹", "新竹市", "hsinchu")),
    City("MiaoliCounty", "苗栗", "Miaoli", 24.5602, 120.8214, ("苗栗", "miaoli")),
    City("Taichung", "台中", "Taichung", 24.1477, 120.6736, ("台中", "臺中", "taichung")),
    City("ChanghuaCounty", "彰化", "Changhua", 24.0518, 120.5161, ("彰化", "changhua")),
    City("NantouCounty", "南投", "Nantou", 23.9609, 120.9719, ("南投", "nantou")),
    City("YunlinCounty", "雲林", "Yunlin", 23.7092, 120.4313, ("雲林", "yunlin")),
    City("ChiayiCounty", "嘉義縣", "Chiayi County", 23.4518, 120.2555, ("嘉義縣", "chiayi county", "chiayicounty")),
    City("Chiayi", "嘉義", "Chiayi", 23.4801, 120.4491, ("嘉義", "嘉義市", "chiayi")),
    City("Tainan", "台南", "Tainan", 22.9999, 120.227, ("台南", "臺南", "tainan")),
    City("Kaohsiung", "高雄", "Kaohsiung", 22.6273, 120.3014, ("高雄", "kaohsiung")),
    City("PingtungCounty", "屏東", "Pingtung", 22.5519, 120.5487, ("屏東", "pingtung")),
    City("YilanCounty", "宜蘭", "Yilan", 24.7021, 121.7378, ("宜蘭", "yilan")),
    City("HualienCounty", "花蓮", "Hualien", 23.9871, 121.601, ("花蓮", "hualien")),
    City("TaitungCounty", "台東", "Taitung", 22.7583, 121.1444, ("台東", "臺東", "taitung")),
    City("PenghuCounty", "澎湖", "Penghu", 23.5711, 119.5794, ("澎湖", "penghu")),
    City("KinmenCounty", "金門", "Kinmen", 24.449, 118.376, ("金門", "kinmen")),
)

_BY_CODE = {c.code: c for c in CITIES}


def _norm(s: str) -> str:
    return " ".join(s.lower().replace("台", "臺").split())


def resolve_city(text: str | None) -> City | None:
    """Match a city code, English or Chinese name. Longest key wins (新竹縣 beats 新竹)."""
    if not text:
        return None
    if text in _BY_CODE:
        return _BY_CODE[text]
    n = _norm(text)
    best: tuple[int, City] | None = None
    for city in CITIES:
        for key in (*city.keys, city.code.lower()):
            k = _norm(key)
            if k and k in n and (best is None or len(k) > best[0]):
                best = (len(k), city)
    return best[1] if best else None


def city_label(code: str | None, lang: str = "en") -> str:
    city = _BY_CODE.get(code or "")
    if not city:
        return code or ""
    return city.zh if lang == "zh" else city.en
