import stations from "./assets/stations.json";
import type { Lang } from "./i18n";

export type ChatHit = {
  id: string;
  name: string | null;
  lat: number;
  lng: number;
  city: string | null;
  source: string;
  km: number;
};

export type ChatReply = { text: string; hits: ChatHit[] };

export type ChatPlace = {
  id: string;
  name: string | null;
  lat: number;
  lng: number;
  city: string | null;
  source: string;
};

type Station = {
  id: string;
  name: string | null;
  lat: number;
  lng: number;
  city: string | null;
  source: string;
};

type City = {
  city: string;
  lat: number;
  lng: number;
  zh: string;
  en: string;
  keys: string[];
};

type Ctx = {
  lang: Lang;
  latitude: number;
  longitude: number;
  battery: number;
  dest: ChatPlace | null;
};

const ALL = stations as Station[];
const SAFETY = 0.85;
const CAPACITY_KWH = 60;
const WH_PER_KM = 180;

const CITIES: City[] = [
  { city: "Keelung", lat: 25.1276, lng: 121.7392, zh: "基隆", en: "Keelung", keys: ["基隆", "keelung"] },
  { city: "Taipei", lat: 25.033, lng: 121.5654, zh: "台北", en: "Taipei", keys: ["台北", "臺北", "taipei"] },
  { city: "NewTaipei", lat: 25.017, lng: 121.463, zh: "新北", en: "New Taipei", keys: ["新北", "new taipei", "newtaipei"] },
  { city: "Taoyuan", lat: 24.993, lng: 121.301, zh: "桃園", en: "Taoyuan", keys: ["桃園", "taoyuan"] },
  { city: "HsinchuCounty", lat: 24.827, lng: 121.012, zh: "新竹縣", en: "Hsinchu County", keys: ["新竹縣", "hsinchu county", "hsinchucounty"] },
  { city: "Hsinchu", lat: 24.8138, lng: 120.9675, zh: "新竹", en: "Hsinchu", keys: ["新竹", "hsinchu"] },
  { city: "MiaoliCounty", lat: 24.5602, lng: 120.8214, zh: "苗栗", en: "Miaoli", keys: ["苗栗", "miaoli"] },
  { city: "Taichung", lat: 24.1477, lng: 120.6736, zh: "台中", en: "Taichung", keys: ["台中", "臺中", "taichung"] },
  { city: "ChanghuaCounty", lat: 24.0518, lng: 120.5161, zh: "彰化", en: "Changhua", keys: ["彰化", "changhua"] },
  { city: "NantouCounty", lat: 23.9609, lng: 120.9719, zh: "南投", en: "Nantou", keys: ["南投", "nantou"] },
  { city: "YunlinCounty", lat: 23.7092, lng: 120.4313, zh: "雲林", en: "Yunlin", keys: ["雲林", "yunlin"] },
  { city: "ChiayiCounty", lat: 23.4518, lng: 120.2555, zh: "嘉義縣", en: "Chiayi County", keys: ["嘉義縣", "chiayi county", "chiayicounty"] },
  { city: "Chiayi", lat: 23.4801, lng: 120.4491, zh: "嘉義", en: "Chiayi", keys: ["嘉義", "chiayi"] },
  { city: "Tainan", lat: 22.9999, lng: 120.227, zh: "台南", en: "Tainan", keys: ["台南", "臺南", "tainan"] },
  { city: "Kaohsiung", lat: 22.6273, lng: 120.3014, zh: "高雄", en: "Kaohsiung", keys: ["高雄", "kaohsiung"] },
  { city: "PingtungCounty", lat: 22.5519, lng: 120.5487, zh: "屏東", en: "Pingtung", keys: ["屏東", "pingtung"] },
  { city: "YilanCounty", lat: 24.7021, lng: 121.7378, zh: "宜蘭", en: "Yilan", keys: ["宜蘭", "yilan"] },
  { city: "HualienCounty", lat: 23.9871, lng: 121.601, zh: "花蓮", en: "Hualien", keys: ["花蓮", "hualien"] },
  { city: "TaitungCounty", lat: 22.7583, lng: 121.1444, zh: "台東", en: "Taitung", keys: ["台東", "臺東", "taitung"] },
  { city: "PenghuCounty", lat: 23.5711, lng: 119.5794, zh: "澎湖", en: "Penghu", keys: ["澎湖", "penghu"] },
  { city: "KinmenCounty", lat: 24.449, lng: 118.376, zh: "金門", en: "Kinmen", keys: ["金門", "kinmen"] },
];

const REGIONS = ["南部", "北部", "中部", "東部", "西部", "south", "northern", "north", "central", "eastern", "east", "western", "west"];

function normText(s: string) {
  return s.toLowerCase().replace(/台/g, "臺").replace(/\s+/g, " ").trim();
}

function fold(s: string) {
  return normText(s).replace(/[\s\-_.]/g, "");
}

export function haversineKm(aLat: number, aLng: number, bLat: number, bLng: number) {
  const R = 6371;
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLng = ((bLng - aLng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((aLat * Math.PI) / 180) * Math.cos((bLat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

export function rangeKm(battery: number) {
  return (SAFETY * ((CAPACITY_KWH * 1000 * battery) / 100)) / WH_PER_KM;
}

function fmtKm(km: number) {
  return km < 10 ? km.toFixed(1) : String(Math.round(km));
}

function cityByCode(code: string | null) {
  return CITIES.find((c) => c.city === code) || null;
}

function cityName(city: City | null, lang: Lang, fallback: string | null) {
  if (!city) return fallback || "";
  return lang === "zh" ? city.zh : city.en;
}

export function cityLabel(code: string | null, lang: Lang) {
  return cityName(cityByCode(code), lang, code);
}

function toHit(s: Station, fromLat: number, fromLng: number): ChatHit {
  return {
    id: s.id,
    name: s.name,
    lat: s.lat,
    lng: s.lng,
    city: s.city,
    source: s.source,
    km: haversineKm(fromLat, fromLng, s.lat, s.lng),
  };
}

function stationName(hit: { name: string | null; id?: string }, lang: Lang) {
  return hit.name || (lang === "zh" ? "未命名充電站" : "Unnamed charger");
}

function matchCity(q: string): { city: City; key: string } | null {
  const n = normText(q);
  let best: { city: City; key: string; len: number } | null = null;
  for (const city of CITIES) {
    for (const key of city.keys) {
      const nk = normText(key);
      if (!nk || !n.includes(nk)) continue;
      if (!best || nk.length > best.len) best = { city, key, len: nk.length };
    }
  }
  return best ? { city: best.city, key: best.key } : null;
}

function mentionsRegion(q: string) {
  const n = normText(q);
  return REGIONS.some((word) => {
    if (/[a-z]/.test(word)) return new RegExp(`\\b${word}\\b`, "i").test(q);
    return n.includes(normText(word));
  });
}

function cutKey(original: string, key: string) {
  const n = normText(original);
  const k = normText(key);
  const i = n.indexOf(k);
  if (i < 0) return original;
  return `${original.slice(0, i)} ${original.slice(i + key.length)}`.replace(/\s+/g, " ").trim();
}

function stripGeneric(s: string) {
  const phrases = [
    "有哪些站",
    "有哪些",
    "有什麼",
    "哪些",
    "幾座",
    "有幾座",
    "有幾",
    "充電站",
    "充電樁",
    "以電量推薦",
    "電量推薦",
    "附近的",
    "最近的",
    "recommend by battery",
    "how many",
    "how far",
    "can i drive",
    "can i reach",
  ];
  let out = s;
  for (const phrase of phrases) {
    out = out.replace(new RegExp(phrase, "ig"), " ");
  }
  out = out.replace(
    /\b(stations|station|chargers|charger|nearby|nearest|closest|recommend|battery|range|in|at|the|me|a|of|for|by|show|list|what|are|there)\b/gi,
    " "
  );
  out = out.replace(/[的嗎呢啊呀？?！!。．，,]/g, " ");
  return out.replace(/\s+/g, " ").trim();
}

function takeNav(q: string) {
  const patterns = [
    /^(?:請|幫我|麻煩)?導航(?:到|去|至)?\s*/,
    /^(?:請|幫我)?(?:帶我去|帶我到|前往|去到)\s*/,
    /^(?:please\s+)?(?:navigate to|take me to|go to|directions to)\s+/i,
  ];
  for (const pattern of patterns) {
    if (pattern.test(q)) return { nav: true, rest: q.replace(pattern, "").trim() };
  }
  return { nav: false, rest: q };
}

function byDistance(hits: ChatHit[]) {
  return [...hits].sort((a, b) => a.km - b.km);
}

function allHits(fromLat: number, fromLng: number, city: string | null) {
  const hits: ChatHit[] = [];
  for (const s of ALL) {
    if (city && s.city !== city) continue;
    hits.push(toHit(s, fromLat, fromLng));
  }
  return byDistance(hits);
}

function searchNames(q: string, fromLat: number, fromLng: number, city: string | null) {
  const needle = fold(q);
  if (needle.length < 2) return [];
  const hits: ChatHit[] = [];
  for (const s of ALL) {
    if (city && s.city !== city) continue;
    const name = fold(s.name || "");
    if (!name.includes(needle)) continue;
    hits.push(toHit(s, fromLat, fromLng));
  }
  return byDistance(hits);
}

function noneText(q: string, lang: Lang) {
  return lang === "zh"
    ? `找不到「${q}」。請寫縣市名稱，例如台北或高雄，或換一個站名。`
    : `Nothing matched “${q}”. Name a city, such as Taipei or Kaohsiung, or try a station name.`;
}

function regionText(lang: Lang) {
  return lang === "zh"
    ? "請寫出縣市名稱，例如台北或高雄，我才能查充電站。"
    : "Name a city, such as Taipei or Kaohsiung, and I can look up chargers there.";
}

function helpText(lang: Lang) {
  return lang === "zh"
    ? "我可以查全台充電站。你可以問附近、某個縣市（例如台北、高雄）、站名，或說「以電量推薦」。點結果就能設成目的地或開始導航。"
    : "I can look up chargers across Taiwan. Ask for nearby stations, a city such as Taipei or Kaohsiung, a station name, or say “recommend by battery”. Tap a result to set it as the destination or start navigation.";
}

export function welcomeText(lang: Lang) {
  return lang === "zh"
    ? "你好，我是充電站助理。可以直接問附近、縣市、站名，或依目前電量推薦。"
    : "Hi! I'm the charger assistant. Ask about nearby chargers, a city, a station name, or which chargers your battery can reach.";
}

export function suggestionChips(lang: Lang) {
  return lang === "zh"
    ? ["附近充電站", "高雄有哪些站", "以電量推薦", "電量夠開多遠"]
    : ["Nearby chargers", "Stations in Kaohsiung", "Recommend by battery", "How far can I drive"];
}

function batteryText(battery: number, lang: Lang) {
  const range = Math.round(rangeKm(battery));
  return lang === "zh"
    ? `目前電量 ${battery}%，估計續航約 ${range} 公里。若要列出開得到的站，可以說「以電量推薦」。`
    : `Battery is ${battery}%, so the estimated range is about ${range} km. Say “recommend by battery” to list chargers you can reach.`;
}

function recommendText(
  battery: number,
  lang: Lang,
  place: string | null,
  hits: ChatHit[],
  total: number,
  shownLimitKm: number
) {
  const range = Math.round(rangeKm(battery));
  const where = place || (lang === "zh" ? "附近" : "nearby");
  if (!total || !hits.length) {
    return lang === "zh"
      ? `以電量 ${battery}% 估計續航約 ${range} 公里，${where}沒有 ${shownLimitKm} 公里內開得到的充電站。`
      : `With ${battery}% battery the range is about ${range} km. No charger within ${shownLimitKm} km${place ? ` in ${place}` : ""}.`;
  }
  const first = hits[0];
  const name = stationName(first, lang);
  return lang === "zh"
    ? `以電量 ${battery}% 估計續航約 ${range} 公里。${where} ${shownLimitKm} 公里內開得到 ${total} 座，最近是${name}（${fmtKm(first.km)} 公里）。`
    : `With ${battery}% battery the range is about ${range} km. ${total} reachable charger${total > 1 ? "s" : ""} within ${shownLimitKm} km${place ? ` in ${place}` : ""}. Closest is ${name} (${fmtKm(first.km)} km).`;
}

function whyText(ctx: Ctx) {
  if (!ctx.dest) {
    return ctx.lang === "zh"
      ? "還沒選充電站。可以先問「附近充電站」或「以電量推薦」。"
      : "No charger is selected yet. Ask for nearby chargers or a battery recommendation.";
  }
  const km = haversineKm(ctx.latitude, ctx.longitude, ctx.dest.lat, ctx.dest.lng);
  const range = rangeKm(ctx.battery);
  const name = stationName(ctx.dest, ctx.lang);
  const where = cityName(cityByCode(ctx.dest.city), ctx.lang, ctx.dest.city);
  const within = km <= range;
  if (ctx.lang === "zh") {
    return `目前選的是${name}${where ? `（${where}）` : ""}，離你 ${fmtKm(km)} 公里。以電量 ${ctx.battery}% 估計續航約 ${Math.round(range)} 公里，這站${within ? "在續航內" : "超出目前續航"}。它排在前面，主要是因為距離比較近。`;
  }
  return `${name}${where ? ` (${where})` : ""} is ${fmtKm(km)} km away. With ${ctx.battery}% battery the range is about ${Math.round(range)} km, so this station is ${within ? "within range" : "beyond the current range"}. It ranks higher mainly because it is closer.`;
}

export function replyTo(raw: string, ctx: Ctx): ChatReply {
  const text = raw.replace(/\s+/g, " ").trim();
  const lang = ctx.lang;
  if (!text) {
    return {
      text: lang === "zh" ? "請輸入問題，例如附近充電站或高雄。" : "Type a question, such as nearby chargers or Kaohsiung.",
      hits: [],
    };
  }
  if (/^(幫助|說明|你能做什麼|你可以做什麼|help|what can you do)\b/i.test(text)) {
    return { text: helpText(lang), hits: [] };
  }
  if (/^(你好|嗨|哈囉|hello|hi|hey)[!！。.\s]*$/i.test(text)) {
    return { text: welcomeText(lang), hits: [] };
  }
  if (/為什麼|為何|why this|why did|why recommend/i.test(text)) {
    return { text: whyText(ctx), hits: [] };
  }

  const { nav, rest } = takeNav(text);
  const query = rest || text;
  const cityHit = matchCity(query);

  if (!cityHit && mentionsRegion(query)) return { text: regionText(lang), hits: [] };

  const recommend = /以電量|電量推薦|推薦|recommend/i.test(query);
  const nearby = /附近|最近|nearby|nearest|closest/i.test(query);
  const reach = /開得到|到得了|夠不夠|能不能開|開得去|開多遠|多遠|夠開|how far|can i reach|can i drive|within range/i.test(query);
  const batteryTalk = /電量|續航|battery|range/i.test(query) || reach;
  const thisOne = /^(這個|這站|目前這個|this one|this|here)$/i.test(query);

  if (nav && thisOne && ctx.dest) {
    const hit: ChatHit = {
      id: ctx.dest.id,
      name: ctx.dest.name,
      lat: ctx.dest.lat,
      lng: ctx.dest.lng,
      city: ctx.dest.city,
      source: ctx.dest.source,
      km: haversineKm(ctx.latitude, ctx.longitude, ctx.dest.lat, ctx.dest.lng),
    };
    const name = stationName(hit, lang);
    return {
      text:
        lang === "zh"
          ? `可以前往目前選的${name}，約 ${fmtKm(hit.km)} 公里。`
          : `You can go to the selected station ${name}, about ${fmtKm(hit.km)} km away.`,
      hits: [hit],
    };
  }

  if (recommend) {
    const limit = Math.min(rangeKm(ctx.battery), 40);
    const pool = allHits(ctx.latitude, ctx.longitude, cityHit?.city.city || null).filter((h) => h.km <= limit);
    const place = cityHit ? cityName(cityHit.city, lang, cityHit.city.city) : null;
    const shown = pool.slice(0, 5);
    return {
      text: recommendText(ctx.battery, lang, place, shown, pool.length, Math.round(limit)),
      hits: shown,
    };
  }

  if (cityHit && batteryTalk) {
    const place = cityName(cityHit.city, lang, cityHit.city.city);
    const away = haversineKm(ctx.latitude, ctx.longitude, cityHit.city.lat, cityHit.city.lng);
    const range = rangeKm(ctx.battery);
    const ok = away <= range;
    const nearest = allHits(ctx.latitude, ctx.longitude, cityHit.city.city).slice(0, 3);
    const verdict =
      lang === "zh"
        ? `${place}離你大約 ${fmtKm(away)} 公里。以電量 ${ctx.battery}% 估計續航約 ${Math.round(range)} 公里，目前${ok ? "開得到" : "開不到"}。`
        : `${place} is about ${fmtKm(away)} km away. With ${ctx.battery}% battery the range is about ${Math.round(range)} km, so you ${ok ? "can reach it" : "cannot reach it yet"}.`;
    return { text: verdict, hits: nearest };
  }

  if (nearby && !cityHit) {
    const pool = allHits(ctx.latitude, ctx.longitude, null);
    const near = pool.filter((h) => h.km <= 10);
    if (!near.length) {
      const closest = pool[0];
      return {
        text:
          lang === "zh"
            ? `10 公里內沒有充電站。最近的是${stationName(closest, lang)}，約 ${fmtKm(closest.km)} 公里。`
            : `No charger within 10 km. The closest is ${stationName(closest, lang)}, about ${fmtKm(closest.km)} km away.`,
        hits: closest ? [closest] : [],
      };
    }
    const range = rangeKm(ctx.battery);
    const extra =
      near[0].km <= range
        ? lang === "zh"
          ? `最近這一站在目前約 ${Math.round(range)} 公里的續航內。`
          : `The closest one is inside the estimated ${Math.round(range)} km range.`
        : lang === "zh"
          ? `最近這一站超出目前約 ${Math.round(range)} 公里的續航。`
          : `The closest one is beyond the estimated ${Math.round(range)} km range.`;
    return {
      text:
        lang === "zh"
          ? `10 公里內有 ${near.length} 座充電站，下面由近到遠。${extra}`
          : `${near.length} ${near.length === 1 ? "charger" : "chargers"} within 10 km, nearest first. ${extra}`,
      hits: near.slice(0, 5),
    };
  }

  if (!cityHit && batteryTalk && !nearby) return { text: batteryText(ctx.battery, lang), hits: [] };

  if (cityHit) {
    const place = cityName(cityHit.city, lang, cityHit.city.city);
    const leftover = stripGeneric(cutKey(query, cityHit.key));
    if (fold(leftover).length >= 2) {
      const found = searchNames(leftover, ctx.latitude, ctx.longitude, cityHit.city.city);
      if (!found.length) return { text: noneText(leftover, lang), hits: [] };
      return {
        text:
          lang === "zh"
            ? `${place}有 ${found.length} 座名稱含「${leftover}」的充電站。`
            : `${found.length} ${place} charger${found.length > 1 ? "s" : ""} match “${leftover}”.`,
        hits: found.slice(0, 5),
      };
    }
    const inCity = allHits(ctx.latitude, ctx.longitude, cityHit.city.city);
    return {
      text:
        lang === "zh"
          ? `${place}有 ${inCity.length} 座充電站。下面是離你較近的幾座。`
          : `${place} has ${inCity.length} ${inCity.length === 1 ? "charger" : "chargers"}. Here are the ones closest to you.`,
      hits: inCity.slice(0, 5),
    };
  }

  const found = searchNames(query, ctx.latitude, ctx.longitude, null);
  if (!found.length) {
    if (fold(query).length < 2) return { text: helpText(lang), hits: [] };
    return { text: noneText(query, lang), hits: [] };
  }
  const lead = found[0];
  const name = stationName(lead, lang);
  if (nav || found.length === 1) {
    return {
      text:
        lang === "zh"
          ? `${found.length > 1 ? `找到 ${found.length} 座相關充電站。` : ""}「${name}」離你約 ${fmtKm(lead.km)} 公里。可以設成目的地，或直接開始導航。`
          : `${found.length > 1 ? `Found ${found.length} matches. ` : ""}${name} is about ${fmtKm(lead.km)} km away. Set it as the destination or start navigation.`,
      hits: found.slice(0, 5),
    };
  }
  return {
    text:
      lang === "zh"
        ? `找到 ${found.length} 座跟「${query}」有關的充電站。點一座就能設成目的地或開始導航。`
        : `Found ${found.length} chargers related to “${query}”. Tap one to set the destination or start navigation.`,
    hits: found.slice(0, 5),
  };
}
