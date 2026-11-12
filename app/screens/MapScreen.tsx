import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import MapView, { Marker, Polyline, PROVIDER_GOOGLE } from "react-native-maps";
import * as Location from "expo-location";
import * as Speech from "expo-speech";
import stations from "../assets/stations.json";
import type { ChatHit } from "../chatbot";
import { useI18n, type Lang } from "../i18n";
import { colors, useTheme } from "../theme";
import { voiceBand, voicePhrase } from "../voice";
import ChatPanel from "./ChatPanel";

type Station = {
  id: string;
  name: string | null;
  lat: number;
  lng: number;
  city: string | null;
  source: string;
};

type SavedPlace = { label: string; latitude: number; longitude: number };
type Coord = { latitude: number; longitude: number };
type OriginPlace = Coord & { label: string; kind: "gps" | "home" | "work" | "map" | "station" };
type NavStep = {
  road: string;
  type: string;
  modifier: string;
  distanceM: number;
  durationS: number;
  cumEndM: number;
  location: Coord;
};

const ALL = stations as Station[];
const FALLBACK = { latitude: 25.033, longitude: 121.5654 };
const KM = 10;
const ME_DELTA = 0.012;
const MAX_PINS = 40;
const CITY_PRESETS: { id: string; city: string | null; lat: number; lng: number; keys: string[] }[] = [
  { id: "nearby", city: null, lat: 0, lng: 0, keys: [] },
  { id: "Keelung", city: "Keelung", lat: 25.1276, lng: 121.7392, keys: ["基隆", "keelung"] },
  { id: "Taipei", city: "Taipei", lat: 25.033, lng: 121.5654, keys: ["台北", "臺北", "taipei"] },
  { id: "NewTaipei", city: "NewTaipei", lat: 25.017, lng: 121.463, keys: ["新北", "newtaipei"] },
  { id: "Taoyuan", city: "Taoyuan", lat: 24.993, lng: 121.301, keys: ["桃園", "taoyuan"] },
  { id: "Hsinchu", city: "Hsinchu", lat: 24.8138, lng: 120.9675, keys: ["新竹", "hsinchu"] },
  { id: "HsinchuCounty", city: "HsinchuCounty", lat: 24.827, lng: 121.012, keys: ["新竹縣"] },
  { id: "MiaoliCounty", city: "MiaoliCounty", lat: 24.5602, lng: 120.8214, keys: ["苗栗", "miaoli"] },
  { id: "Taichung", city: "Taichung", lat: 24.1477, lng: 120.6736, keys: ["台中", "臺中", "taichung"] },
  { id: "ChanghuaCounty", city: "ChanghuaCounty", lat: 24.0518, lng: 120.5161, keys: ["彰化", "changhua"] },
  { id: "NantouCounty", city: "NantouCounty", lat: 23.9609, lng: 120.9719, keys: ["南投", "nantou"] },
  { id: "YunlinCounty", city: "YunlinCounty", lat: 23.7092, lng: 120.4313, keys: ["雲林", "yunlin"] },
  { id: "Chiayi", city: "Chiayi", lat: 23.4801, lng: 120.4491, keys: ["嘉義", "chiayi"] },
  { id: "ChiayiCounty", city: "ChiayiCounty", lat: 23.4518, lng: 120.2555, keys: ["嘉義縣"] },
  { id: "Tainan", city: "Tainan", lat: 22.9999, lng: 120.227, keys: ["台南", "臺南", "tainan"] },
  { id: "Kaohsiung", city: "Kaohsiung", lat: 22.6273, lng: 120.3014, keys: ["高雄", "kaohsiung"] },
  { id: "PingtungCounty", city: "PingtungCounty", lat: 22.5519, lng: 120.5487, keys: ["屏東", "pingtung"] },
  { id: "YilanCounty", city: "YilanCounty", lat: 24.7021, lng: 121.7378, keys: ["宜蘭", "yilan"] },
  { id: "HualienCounty", city: "HualienCounty", lat: 23.9871, lng: 121.601, keys: ["花蓮", "hualien"] },
  { id: "TaitungCounty", city: "TaitungCounty", lat: 22.7583, lng: 121.1444, keys: ["台東", "臺東", "taitung"] },
  { id: "PenghuCounty", city: "PenghuCounty", lat: 23.5711, lng: 119.5794, keys: ["澎湖", "penghu"] },
  { id: "KinmenCounty", city: "KinmenCounty", lat: 24.449, lng: 118.376, keys: ["金門", "kinmen"] },
];
const WH_PER_KM = 180;
const CAPACITY_KWH = 60;
const SAFETY = 0.85;

const LIGHT_MAP = [
  { elementType: "geometry", stylers: [{ color: "#f3f1ea" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#5c6b73" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#f3f1ea" }] },
  { featureType: "administrative", elementType: "geometry.stroke", stylers: [{ color: "#d9d4c8" }] },
  { featureType: "landscape.natural", elementType: "geometry", stylers: [{ color: "#e4f0df" }] },
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "poi.park", stylers: [{ visibility: "on" }] },
  { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#c9e4c0" }] },
  { featureType: "poi.park", elementType: "labels", stylers: [{ visibility: "off" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#ffffff" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#e6e1d4" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#f6e7c4" }] },
  { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#e6d6ad" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#c5def2" }] },
  { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#6d90aa" }] },
];

const DARK_MAP = [
  { elementType: "geometry", stylers: [{ color: "#1b2838" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#8aa4b8" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#1b2838" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#30475e" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#1b2838" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#3d5a73" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#0e1a26" }] },
  { featureType: "poi", elementType: "geometry", stylers: [{ color: "#243447" }] },
  { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#1a3a32" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
];

function haversineKm(aLat: number, aLng: number, bLat: number, bLng: number) {
  const R = 6371;
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLng = ((bLng - aLng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((aLat * Math.PI) / 180) *
      Math.cos((bLat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

function moveByMeters(pos: Coord, bearing: number, meters: number): Coord {
  const rad = (bearing * Math.PI) / 180;
  const latRad = (pos.latitude * Math.PI) / 180;
  return {
    latitude: pos.latitude + (meters * Math.cos(rad)) / 111320,
    longitude: pos.longitude + (meters * Math.sin(rad)) / (111320 * Math.cos(latRad) || 1),
  };
}

function bearingDeg(from: Coord, to: Coord) {
  const φ1 = (from.latitude * Math.PI) / 180;
  const φ2 = (to.latitude * Math.PI) / 180;
  const Δλ = ((to.longitude - from.longitude) * Math.PI) / 180;
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function nearestOnLine(
  line: Coord[],
  pos: Coord
): { point: Coord; index: number; bearing: number; distM: number } {
  if (line.length === 1) {
    return {
      point: line[0],
      index: 0,
      bearing: 0,
      distM: haversineKm(pos.latitude, pos.longitude, line[0].latitude, line[0].longitude) * 1000,
    };
  }
  let bestD = Number.POSITIVE_INFINITY;
  let best = line[0];
  let bestI = 0;
  for (let i = 0; i < line.length - 1; i++) {
    const a = line[i];
    const b = line[i + 1];
    const vx = b.longitude - a.longitude;
    const vy = b.latitude - a.latitude;
    const c2 = vx * vx + vy * vy;
    const t =
      c2 === 0
        ? 0
        : Math.max(
            0,
            Math.min(1, ((pos.longitude - a.longitude) * vx + (pos.latitude - a.latitude) * vy) / c2)
          );
    const p = {
      latitude: a.latitude + vy * t,
      longitude: a.longitude + vx * t,
    };
    const d = haversineKm(pos.latitude, pos.longitude, p.latitude, p.longitude);
    if (d < bestD) {
      bestD = d;
      best = p;
      bestI = i;
    }
  }
  const nxt = line[Math.min(bestI + 1, line.length - 1)];
  return { point: best, index: bestI, bearing: bearingDeg(best, nxt), distM: bestD * 1000 };
}

function splitRoute(line: Coord[], pos: Coord) {
  const snap = nearestOnLine(line, pos);
  const done = line.slice(0, snap.index + 1).concat(snap.point);
  const remain = [snap.point].concat(line.slice(snap.index + 1));
  return { done, remain };
}

function nearestIndex(line: Coord[], pos: Coord) {
  let bestI = 0;
  let best = Number.POSITIVE_INFINITY;
  for (let i = 0; i < line.length; i++) {
    const d = haversineKm(pos.latitude, pos.longitude, line[i].latitude, line[i].longitude);
    if (d < best) {
      best = d;
      bestI = i;
    }
  }
  return bestI;
}

function alongMeters(line: Coord[], index: number) {
  let m = 0;
  for (let i = 1; i <= index && i < line.length; i++) {
    m += haversineKm(line[i - 1].latitude, line[i - 1].longitude, line[i].latitude, line[i].longitude) * 1000;
  }
  return m;
}

function normText(s: string) {
  return s.toLowerCase().replace(/台/g, "臺");
}

function matchPreset(q: string) {
  const n = normText(q);
  return CITY_PRESETS.find((p) => p.keys.some((k) => n.includes(normText(k)) || normText(k).includes(n)));
}

function nationwideHits(q: string, from: Coord): Station[] {
  const raw = q.trim();
  if (!raw) return [];
  const n = normText(raw);
  const preset = matchPreset(raw);
  return ALL.map((s) => ({
    s,
    d: haversineKm(from.latitude, from.longitude, s.lat, s.lng),
  }))
    .filter(({ s }) => {
      if (preset?.city) return s.city === preset.city;
      const name = normText(s.name || "");
      const city = normText(s.city || "");
      return name.includes(n) || city.includes(n);
    })
    .sort((a, b) => a.d - b.d)
    .slice(0, 40)
    .map((x) => x.s);
}

type Suggest = {
  id: string;
  label: string;
  sub: string;
  latitude: number;
  longitude: number;
};

async function searchTyped(q: string, from: Coord): Promise<Suggest[]> {
  const local = nationwideHits(q, from)
    .slice(0, 6)
    .map((s) => ({
      id: s.id,
      label: s.name || s.id,
      sub: s.city || "",
      latitude: s.lat,
      longitude: s.lng,
    }));
  let remote: Suggest[] = [];
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=tw&q=${encodeURIComponent(q)}`,
      { headers: { "Accept-Language": "zh-TW" } }
    );
    const data = await res.json();
    remote = (Array.isArray(data) ? data : []).map((p: { place_id?: number; name?: string; display_name: string; lat: string; lon: string }, i: number) => ({
      id: `osm-${p.place_id ?? i}`,
      label: p.name || p.display_name.split(",")[0],
      sub: p.display_name,
      latitude: Number(p.lat),
      longitude: Number(p.lon),
    }));
  } catch {
    /* nominatim optional */
  }
  const seen = new Set(local.map((x) => x.label));
  return [...local, ...remote.filter((r) => !seen.has(r.label))].slice(0, 10);
}

function nearbyStations(lat: number, lng: number, km = KM): Station[] {
  return ALL.map((s) => ({ s, d: haversineKm(lat, lng, s.lat, s.lng) }))
    .filter((x) => x.d <= km)
    .sort((a, b) => a.d - b.d)
    .slice(0, MAX_PINS)
    .map((x) => x.s);
}

type MapRegion = Coord & { latitudeDelta: number; longitudeDelta: number };
type Cluster = { id: string; lat: number; lng: number; count: number };

function stationsInView(list: Station[], view: MapRegion) {
  const latHalf = (view.latitudeDelta / 2) * 1.2;
  const lngHalf = (view.longitudeDelta / 2) * 1.2;
  return list.filter(
    (s) => Math.abs(s.lat - view.latitude) <= latHalf && Math.abs(s.lng - view.longitude) <= lngHalf
  );
}

function clusterStations(list: Station[], latDelta: number): { bubbles: Cluster[]; pins: Station[] } {
  const close = latDelta < 0.1;
  if (close && list.length <= 70) return { bubbles: [], pins: list };
  const cell = Math.max(latDelta / (close ? 7 : 5.2), close ? 0.02 : 0.03);
  const buckets = new Map<string, Station[]>();
  for (const s of list) {
    const key = `${Math.floor(s.lng / cell)}:${Math.floor(s.lat / cell)}`;
    const group = buckets.get(key);
    if (group) group.push(s);
    else buckets.set(key, [s]);
  }
  const bubbles: Cluster[] = [];
  const pins: Station[] = [];
  for (const [id, group] of buckets) {
    if (group.length === 1) {
      pins.push(group[0]);
      continue;
    }
    let lat = 0;
    let lng = 0;
    for (const s of group) {
      lat += s.lat;
      lng += s.lng;
    }
    bubbles.push({ id, lat: lat / group.length, lng: lng / group.length, count: group.length });
  }
  return { bubbles, pins };
}

function maneuverArrow(type: string, modifier: string) {
  const m = modifier.toLowerCase();
  const ty = type.toLowerCase();
  if (ty === "arrive") return "●";
  if (ty.includes("uturn") || m === "uturn") return "↩";
  if (m.includes("left") || ty.includes("left")) return "↰";
  if (m.includes("right") || ty.includes("right")) return "↱";
  return "↑";
}

function maneuverTitle(
  lang: Lang,
  type: string,
  modifier: string,
  road: string,
  fallbackRoad: string,
  arrived: string,
  continueStraight: string
) {
  const name = road || fallbackRoad;
  const m = modifier.toLowerCase();
  const ty = type.toLowerCase();
  if (ty === "arrive") return arrived;
  if (ty === "depart" || ty === "continue" || ty === "new name" || ty === "notification") {
    return name || continueStraight;
  }
  if (lang === "zh") {
    if (m === "uturn" || ty.includes("uturn")) return `迴轉上${name}`;
    if (m.includes("slight") && m.includes("left")) return `靠左走${name}`;
    if (m.includes("slight") && m.includes("right")) return `靠右走${name}`;
    if (m.includes("left")) return `左轉${name}`;
    if (m.includes("right")) return `右轉${name}`;
    return name;
  }
  if (m === "uturn" || ty.includes("uturn")) return `U-turn onto ${name}`;
  if (m.includes("slight") && m.includes("left")) return `Keep left on ${name}`;
  if (m.includes("slight") && m.includes("right")) return `Keep right on ${name}`;
  if (m.includes("left")) return `Turn left onto ${name}`;
  if (m.includes("right")) return `Turn right onto ${name}`;
  return name;
}

function zhCount(n: number) {
  const digit = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
  if (n < 10) return digit[n];
  if (n === 10) return "十";
  if (n < 20) return `十${digit[n % 10]}`;
  if (n < 100) {
    const tens = Math.floor(n / 10);
    const ones = n % 10;
    return `${digit[tens]}十${ones ? digit[ones] : ""}`;
  }
  return String(n);
}

function formatDriveTime(totalMin: number, lang: Lang) {
  const mins = Math.max(1, Math.round(totalMin));
  if (mins < 60) return lang === "zh" ? `${mins}分鐘` : `${mins} min`;
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  if (lang === "zh") {
    const hourText = hours === 1 ? "一個小時" : `${zhCount(hours)}個小時`;
    return rest === 0 ? hourText : `${hourText}${zhCount(rest)}分鐘`;
  }
  const hourText = hours === 1 ? "1 hour" : `${hours} hours`;
  return rest === 0 ? hourText : `${hourText} ${rest} min`;
}

function formatArrival(remainS: number, lang: Lang) {
  const d = new Date(Date.now() + remainS * 1000);
  const h = d.getHours();
  const min = d.getMinutes().toString().padStart(2, "0");
  if (lang === "zh") {
    const ap = h < 12 ? "上午" : "下午";
    return `${ap}${h % 12 || 12}:${min}`;
  }
  const ap = h < 12 ? "AM" : "PM";
  return `${h % 12 || 12}:${min} ${ap}`;
}

type Props = { onLogout: () => void };

function useStyles() {
  const { dark } = useTheme();
  return useMemo(() => makeStyles(dark), [dark]);
}

function DarkModeRow({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  const { dark, setDark } = useTheme();
  const styles = useStyles();
  return (
    <View style={[compact ? styles.langRow : styles.menuRow, compact && { justifyContent: "space-between" }]}>
      <Text style={compact ? styles.darkLabel : styles.menuRowTxt}>{t.darkMode}</Text>
      <Switch
        value={dark}
        onValueChange={setDark}
        trackColor={{ false: "#9ca3af", true: "#16a34a" }}
        thumbColor="#ffffff"
      />
    </View>
  );
}

function BatterySlider({
  value,
  onChange,
  onDragStart,
  onDragEnd,
}: {
  value: number;
  onChange: (next: number) => void;
  onDragStart?: () => void;
  onDragEnd?: () => void;
}) {
  const styles = useStyles();
  const widthRef = useRef(1);

  const setFromX = (x: number) => {
    const pct = Math.round(Math.min(100, Math.max(0, (x / widthRef.current) * 100)));
    onChange(pct);
  };

  return (
    <View
      style={styles.sliderHit}
      onLayout={(e) => {
        widthRef.current = Math.max(1, e.nativeEvent.layout.width);
      }}
      onStartShouldSetResponder={() => true}
      onMoveShouldSetResponder={() => true}
      onResponderTerminationRequest={() => false}
      onResponderGrant={(e) => {
        onDragStart?.();
        setFromX(e.nativeEvent.locationX);
      }}
      onResponderMove={(e) => setFromX(e.nativeEvent.locationX)}
      onResponderRelease={() => onDragEnd?.()}
      onResponderTerminate={() => onDragEnd?.()}
    >
      <View style={styles.sliderTrack}>
        <View style={[styles.sliderFill, { width: `${value}%` }]} />
      </View>
      <View pointerEvents="none" style={[styles.sliderThumb, { left: `${value}%` }]} />
    </View>
  );
}

export default function MapScreen({ onLogout }: Props) {
  const { t, lang, setLang } = useI18n();
  const { dark } = useTheme();
  const styles = useStyles();
  const ink = colors(dark);
  const mapRef = useRef<MapView>(null);
  const watchRef = useRef<Location.LocationSubscription | null>(null);
  const headingWatchRef = useRef<Location.LocationSubscription | null>(null);
  const lineRef = useRef<Coord[]>([]);
  const stepsRef = useRef<NavStep[]>([]);
  const totalMRef = useRef(1);
  const totalSRef = useRef(1);
  const navigatingRef = useRef(false);
  const headingLiveRef = useRef(0);
  const lastCamRef = useRef(0);
  const followLockRef = useRef(false);
  const mapHeadingRef = useRef(0);
  const lastHeadPoll = useRef(0);
  const coordRef = useRef(FALLBACK);
  const magRef = useRef<{ remove: () => void } | null>(null);
  const magOkRef = useRef(false);
  const compassOkRef = useRef(false);
  const destRef = useRef<Station | null>(null);
  const routingRef = useRef(false);
  const lastRerouteRef = useRef(0);
  const langRef = useRef(lang);
  const voiceOnRef = useRef(true);
  const voiceCueRef = useRef("");
  const navCamLockRef = useRef(true);
  const camHeadRef = useRef(0);
  const driveBearingRef = useRef(0);
  langRef.current = lang;

  const [coord, setCoord] = useState(FALLBACK);
  const [heading, setHeading] = useState(0);
  const [gpsReady, setGpsReady] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [battery, setBattery] = useState(80);
  const [menuScroll, setMenuScroll] = useState(true);
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<Coord | null>(null);
  const [searchHits, setSearchHits] = useState<Station[]>([]);
  const [regionId, setRegionId] = useState("nearby");
  const [chip, setChip] = useState<"charger" | "home" | "work" | "food">("charger");
  const [tab, setTab] = useState<"explore" | "settings">("explore");
  const [home, setHome] = useState<SavedPlace | null>(null);
  const [work, setWork] = useState<SavedPlace | null>(null);
  const [picked, setPicked] = useState<Station[]>([]);
  const [shortlist, setShortlist] = useState<Station[]>([]);
  const [choosing, setChoosing] = useState(false);
  const [dest, setDest] = useState<Station | null>(null);
  destRef.current = dest;
  const [status, setStatus] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [dock, setDock] = useState<null | "search" | "filter" | "menu" | "help">(null);
  const [view, setView] = useState<MapRegion>({
    ...FALLBACK,
    latitudeDelta: 0.08,
    longitudeDelta: 0.08,
  });
  const [mapHeading, setMapHeading] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const [routeLine, setRouteLine] = useState<Coord[]>([]);
  const [routeMeta, setRouteMeta] = useState<{ km: string; min: string; steps: string[] } | null>(
    null
  );
  const [routing, setRouting] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const [navSteps, setNavSteps] = useState<NavStep[]>([]);
  const [voiceOn, setVoiceOn] = useState(true);
  const [driveHeading, setDriveHeading] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const [remainM, setRemainM] = useState(0);
  const [remainS, setRemainS] = useState(0);
  const [snapPos, setSnapPos] = useState<Coord | null>(null);
  const [origin, setOrigin] = useState<OriginPlace | null>(null);
  const [pickMode, setPickMode] = useState<"origin" | "dest" | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [tripOpen, setTripOpen] = useState(false);
  const [activeField, setActiveField] = useState<"origin" | "dest">("origin");
  const [originQuery, setOriginQuery] = useState("");
  const [destQuery, setDestQuery] = useState("");
  const [suggests, setSuggests] = useState<Suggest[]>([]);

  const goTo = (latitude: number, longitude: number, delta = 0.08) => {
    mapRef.current?.animateToRegion({
      latitude,
      longitude,
      latitudeDelta: delta,
      longitudeDelta: delta,
    });
  };

  const centerOnMe = (pos: Coord, delta = ME_DELTA, force = false) => {
    const now = Date.now();
    if (!force && now - lastCamRef.current < 180) return;
    lastCamRef.current = now;
    mapRef.current?.animateToRegion(
      {
        latitude: pos.latitude,
        longitude: pos.longitude,
        latitudeDelta: delta,
        longitudeDelta: delta,
      },
      450
    );
  };

  const followUser = (pos: Coord, force = false, course?: number) => {
    const raw = (((course ?? driveBearingRef.current) % 360) + 360) % 360;
    driveBearingRef.current = raw;
    setDriveHeading((prev) => {
      const diff = Math.abs(raw - prev);
      const delta = Math.min(diff, 360 - diff);
      return delta < 4 ? prev : raw;
    });
    if (!force && !navCamLockRef.current) return;
    const now = Date.now();
    if (!force && now - lastCamRef.current < 160) return;
    lastCamRef.current = now;
    const prevCam = camHeadRef.current;
    let turn = ((raw - prevCam + 540) % 360) - 180;
    if (!force) turn = Math.max(-75, Math.min(75, turn));
    const camHeading = (prevCam + turn + 360) % 360;
    camHeadRef.current = camHeading;
    mapHeadingRef.current = camHeading;
    setMapHeading(camHeading);
    mapRef.current?.animateCamera(
      {
        center: moveByMeters(pos, camHeading, 80),
        heading: camHeading,
        pitch: 50,
        altitude: 420,
        zoom: 17.6,
      },
      { duration: force ? 500 : 280 }
    );
  };

  const syncMapHeading = (force = false) => {
    const now = Date.now();
    if (!force && now - lastHeadPoll.current < 40) return;
    lastHeadPoll.current = now;
    mapRef.current
      ?.getCamera()
      .then((cam) => {
        const next = ((cam.heading ?? 0) % 360 + 360) % 360;
        const prev = mapHeadingRef.current;
        const diff = Math.abs(next - prev);
        const delta = Math.min(diff, 360 - diff);
        if (delta < 1) return;
        mapHeadingRef.current = next;
        setMapHeading(next);
      })
      .catch(() => {});
  };

  const resetNorth = () => {
    mapRef.current?.getCamera().then((cam) => {
      mapRef.current?.animateCamera({ ...cam, heading: 0 }, { duration: 350 });
    });
  };

  const applyHeading = (value: number | null | undefined) => {
    if (value == null || !Number.isFinite(value) || value < 0) return;
    const next = ((value % 360) + 360) % 360;
    const prev = headingLiveRef.current;
    const diff = Math.abs(next - prev);
    const delta = Math.min(diff, 360 - diff);
    if (delta < 3) return;
    headingLiveRef.current = next;
    setHeading(next);
    if (navigatingRef.current) followUser(coordRef.current, false, next);
  };

  const fetchAndApplyRoute = async (
    from: Coord,
    to: { lat: number; lng: number; name?: string | null },
    opts?: { silent?: boolean; preview?: boolean }
  ) => {
    if (routingRef.current) return;
    routingRef.current = true;
    if (!opts?.silent) {
      setRouting(true);
      setStatus(t.routingLong);
    } else {
      setStatus(t.rerouting);
    }
    try {
      const url =
        `https://router.project-osrm.org/route/v1/driving/` +
        `${from.longitude},${from.latitude};${to.lng},${to.lat}` +
        `?overview=full&geometries=geojson&steps=true&radiuses=300;300`;
      const res = await fetch(url);
      const data = await res.json();
      if (data.code !== "Ok" || !data.routes?.[0]) {
        throw new Error(data.message || "no route");
      }
      const route = data.routes[0];
      const line = (route.geometry.coordinates as [number, number][]).map(([lng, lat]) => ({
        latitude: lat,
        longitude: lng,
      }));
      const parsed: NavStep[] = [];
      let cum = 0;
      for (const leg of route.legs || []) {
        for (const step of leg.steps || []) {
          cum += step.distance || 0;
          const loc = step.maneuver?.location as [number, number] | undefined;
          parsed.push({
            road: step.name || t.road,
            type: step.maneuver?.type || "continue",
            modifier: step.maneuver?.modifier || "",
            distanceM: step.distance || 0,
            durationS: step.duration || 0,
            cumEndM: cum,
            location: loc ? { latitude: loc[1], longitude: loc[0] } : line[0],
          });
        }
      }
      const strSteps = parsed.map((s) => `${s.type} ${s.modifier} ${s.road}`.trim());
      lineRef.current = line;
      stepsRef.current = parsed;
      totalMRef.current = route.distance || 1;
      totalSRef.current = route.duration || 1;
      setRouteLine(line);
      setNavSteps(parsed);
      setStepIndex(0);
      setRemainM(route.distance || 0);
      setRemainS(route.duration || 0);
      setRouteMeta({
        km: (route.distance / 1000).toFixed(1),
        min: formatDriveTime(route.duration / 60, lang),
        steps: strSteps.slice(0, 12),
      });
      setMenuOpen(false);
      if (!opts?.preview) setTripOpen(false);
      const snap = nearestOnLine(line, from);
      const puck = snap.distM > 12 ? from : snap.point;
      setSnapPos(puck);
      if (!compassOkRef.current) applyHeading(snap.bearing);
      setStatus(t.inAppNav(formatDriveTime(route.duration / 60, lang), (route.distance / 1000).toFixed(1)));
      voiceCueRef.current = "";
      if (opts?.preview) {
        navigatingRef.current = false;
        setNavigating(false);
        setPreviewing(true);
        mapRef.current?.fitToCoordinates(line, {
          edgePadding: { top: 80, right: 40, bottom: 180, left: 40 },
          animated: true,
        });
      } else {
        navigatingRef.current = true;
        navCamLockRef.current = true;
        setPreviewing(false);
        setNavigating(true);
        followUser(
          puck,
          true,
          compassOkRef.current || magOkRef.current ? headingLiveRef.current : snap.bearing
        );
        announce(0);
      }
    } catch {
      if (!opts?.silent) {
        Alert.alert(t.routeFailTitle, t.routeFailBody);
        setStatus(t.routeFailStatus);
      }
    } finally {
      routingRef.current = false;
      setRouting(false);
    }
  };

  const announce = (along: number) => {
    if (!voiceOnRef.current) return;
    const steps = stepsRef.current;
    if (steps.length === 0) return;
    let index = steps.findIndex((step) => step.cumEndM > along + 8);
    if (index < 0) index = steps.length - 1;
    const current = steps[index];
    const upcoming = steps[index + 1] ?? current;
    const distanceM = Math.max(0, current.cumEndM - along);
    const band = voiceBand(distanceM);
    if (!band) return;
    const key = `${index}:${band}`;
    if (voiceCueRef.current === key) return;
    const phrase = voicePhrase(langRef.current, upcoming, current.road, distanceM, band);
    voiceCueRef.current = key;
    if (!phrase) return;
    void Speech.stop().then(() => {
      if (voiceCueRef.current !== key || !voiceOnRef.current) return;
      Speech.speak(phrase, {
        language: langRef.current === "zh" ? "zh-TW" : "en-US",
        rate: 0.95,
        useApplicationAudioSession: false,
      });
    });
  };

  const updateProgress = (pos: Coord) => {
    const line = lineRef.current;
    const steps = stepsRef.current;
    if (line.length < 2) return;
    const snap = nearestOnLine(line, pos);
    const puck = snap.distM > 12 ? pos : snap.point;
    setSnapPos(puck);
    const course =
      compassOkRef.current || magOkRef.current ? headingLiveRef.current : snap.bearing;
    followUser(puck, false, course);
    if (snap.distM <= 28) {
      const idx = nearestIndex(line, pos);
      const along = alongMeters(line, idx);
      const leftM = Math.max(0, totalMRef.current - along);
      const ratio = leftM / Math.max(1, totalMRef.current);
      setRemainM(leftM);
      setRemainS(Math.max(30, totalSRef.current * ratio));
      let si = steps.findIndex((s) => s.cumEndM > along + 8);
      if (si < 0) si = Math.max(0, steps.length - 1);
      setStepIndex(si);
      announce(along);
      if (!compassOkRef.current && !magOkRef.current) applyHeading(snap.bearing);
      return;
    }
    const d = destRef.current;
    const now = Date.now();
    if (d && now - lastRerouteRef.current > 4000) {
      lastRerouteRef.current = now;
      void fetchAndApplyRoute(pos, d, { silent: true });
    }
  };

  const locate = async (silent = false) => {
    setGpsError(null);
    const { status: perm } = await Location.requestForegroundPermissionsAsync();
    if (perm !== "granted") {
      setGpsError(t.noGpsStatus);
      setGpsReady(true);
      if (!silent) Alert.alert(t.noGpsTitle, t.noGpsBody);
      return;
    }
    const pos = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.BestForNavigation,
    });
    const next = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
    setCoord(next);
    coordRef.current = next;
    if ((pos.coords.speed ?? 0) > 1) applyHeading(pos.coords.heading);
    setGpsReady(true);
    setStatus(t.posStatus(next.latitude.toFixed(4), next.longitude.toFixed(4)));
    followLockRef.current = true;
    centerOnMe(next, ME_DELTA, true);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { status: perm } = await Location.requestForegroundPermissionsAsync();
        if (perm !== "granted") {
          setGpsError(t.noGpsStatus);
          setGpsReady(true);
          return;
        }
        try {
          const sensors = await import("expo-sensors");
          await sensors.Magnetometer.requestPermissionsAsync?.();
        } catch {
          /* sensors optional */
        }
        const pos = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.BestForNavigation,
        });
        if (cancelled) return;
        const next = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
        setCoord(next);
        coordRef.current = next;
        setGpsReady(true);
        setStatus(t.posStatus(next.latitude.toFixed(4), next.longitude.toFixed(4)));
        goTo(next.latitude, next.longitude, 0.01);

        watchRef.current = await Location.watchPositionAsync(
          {
            accuracy: Location.Accuracy.BestForNavigation,
            timeInterval: 800,
            distanceInterval: 1,
          },
          (p) => {
            const here = { latitude: p.coords.latitude, longitude: p.coords.longitude };
            coordRef.current = here;
            setCoord(here);
            if (!magOkRef.current && (p.coords.speed ?? 0) > 1.2) applyHeading(p.coords.heading);
            if (navigatingRef.current) updateProgress(here);
            else if (followLockRef.current) centerOnMe(here, ME_DELTA);
          }
        );
        try {
          headingWatchRef.current = await Location.watchHeadingAsync((h) => {
            const hd = h.trueHeading >= 0 ? h.trueHeading : h.magHeading;
            if (hd >= 0) {
              compassOkRef.current = true;
              applyHeading(hd);
            }
          });
        } catch {
          /* fallback magnetometer */
        }
        try {
          const sensors = await import("expo-sensors");
          const magOk = await sensors.Magnetometer.isAvailableAsync();
          if (magOk) {
            sensors.Magnetometer.setUpdateInterval(120);
            magRef.current = sensors.Magnetometer.addListener(({ x, y }) => {
              if (compassOkRef.current) return;
              magOkRef.current = true;
              let deg = (Math.atan2(-x, y) * 180) / Math.PI;
              if (deg < 0) deg += 360;
              applyHeading(deg);
            });
          }
        } catch {
          /* compass fallback only */
        }
      } catch {
        setGpsError(t.gpsFail);
        setGpsReady(true);
      }
    })();
    return () => {
      cancelled = true;
      watchRef.current?.remove();
      headingWatchRef.current?.remove();
      magRef.current?.remove();
    };
  }, []);

  useEffect(() => {
    if (!tripOpen) return;
    const q = (activeField === "origin" ? originQuery : destQuery).trim();
    if (q.length < 2 || q === t.yourLocation || q === t.home || q === t.work) {
      setSuggests([]);
      return;
    }
    const handle = setTimeout(() => {
      searchTyped(q, coordRef.current).then(setSuggests);
    }, 350);
    return () => clearTimeout(handle);
  }, [originQuery, destQuery, activeField, tripOpen, t.yourLocation, t.home, t.work]);

  const endNavigation = () => {
    navigatingRef.current = false;
    navCamLockRef.current = false;
    camHeadRef.current = 0;
    mapHeadingRef.current = 0;
    setMapHeading(0);
    voiceCueRef.current = "";
    void Speech.stop();
    setNavigating(false);
    setPreviewing(false);
    setSnapPos(null);
    setRouteLine([]);
    mapRef.current?.animateCamera(
      {
        center: coordRef.current,
        heading: 0,
        pitch: 0,
        altitude: 1400,
        zoom: 15,
      },
      { duration: 450 }
    );
  };

  const unlockStation = (closeMenu = false) => {
    setDest(null);
    setPreviewing(false);
    setRouteLine([]);
    setRouteMeta(null);
    setSnapPos(null);
    if (closeMenu) setMenuOpen(false);
    setStatus(t.stationUnlocked);
  };

  const pinOrigin = focus || coord;
  const pins = useMemo(
    () => nearbyStations(pinOrigin.latitude, pinOrigin.longitude, focus ? 18 : KM),
    [pinOrigin.latitude, pinOrigin.longitude, focus]
  );
  const shown = useMemo(() => {
    if (searchHits.length) return searchHits;
    return pins;
  }, [pins, searchHits]);

  const mapMarks = useMemo(() => {
    if (navigating || (chip !== "charger" && chip !== "food")) {
      return { bubbles: [] as Cluster[], pins: [] as Station[] };
    }
    const preset = CITY_PRESETS.find((p) => p.id === regionId);
    const regionPool = preset?.city ? ALL.filter((s) => s.city === preset.city) : ALL;
    const showArea = choosing || (shortlist.length > 0 && !!dest);
    const base = showArea ? regionPool : searchHits.length ? searchHits : ALL;
    const clustered = clusterStations(stationsInView(base, view), view.latitudeDelta);
    if (!choosing) return clustered;
    const seen = new Set(clustered.pins.map((p) => p.id));
    return { ...clustered, pins: clustered.pins.concat(shortlist.filter((s) => !seen.has(s.id))) };
  }, [navigating, chip, searchHits, view, choosing, shortlist, dest, regionId]);

  const onChip = (next: typeof chip) => {
    setChip(next);
    setPicked([]);
    if (next === "charger") {
      setStatus(t.nearbyChargers(shown.length, KM));
      return;
    }
    if (next === "home") {
      if (home) {
        goTo(home.latitude, home.longitude, 0.04);
        setStatus(t.movedHome);
      } else {
        Alert.alert(t.homeHelpTitle, t.homeHelpBody);
      }
      return;
    }
    if (next === "work") {
      if (work) {
        goTo(work.latitude, work.longitude, 0.04);
        setStatus(t.movedWork);
      } else {
        Alert.alert(t.workHelpTitle, t.workHelpBody);
      }
      return;
    }
    Alert.alert(t.foodTitle, t.foodBody);
    setChip("charger");
  };

  const applyRegion = (id: string) => {
    setRegionId(id);
    setChip("charger");
    setPicked([]);
    setChoosing(false);
    setShortlist([]);
    if (!navigatingRef.current) {
      setDest(null);
      setPreviewing(false);
      setRouteLine([]);
      setRouteMeta(null);
    }
    const preset = CITY_PRESETS.find((p) => p.id === id);
    if (!preset || id === "nearby") {
      setFocus(null);
      setSearchHits([]);
      setQuery("");
      goTo(coord.latitude, coord.longitude, 0.04);
      setStatus(t.nearbyChargers(nearbyStations(coord.latitude, coord.longitude).length, KM));
      return;
    }
    const center = { latitude: preset.lat, longitude: preset.lng };
    setFocus(center);
    const hits = ALL.filter((s) => s.city === preset.city).slice(0, 40);
    const near = nearbyStations(center.latitude, center.longitude, 18);
    setSearchHits(near.length ? near : hits);
    setQuery(preset.keys[0]);
    goTo(center.latitude, center.longitude, 0.18);
    const label = lang === "zh" ? preset.keys[0] : preset.id;
    setStatus(t.foundIn(near.length || hits.length, label));
  };

  const runPlaceSearch = () => {
    const q = query.trim();
    if (!q) {
      applyRegion("nearby");
      return;
    }
    const hits = nationwideHits(q, coord);
    setChip("charger");
    if (hits.length === 0) {
      Alert.alert(t.noStationTitle, t.noSearchHits);
      setStatus(t.noSearchHits);
      return;
    }
    const preset = matchPreset(q);
    const center = preset
      ? { latitude: preset.lat, longitude: preset.lng }
      : { latitude: hits[0].lat, longitude: hits[0].lng };
    setFocus(center);
    setSearchHits(hits);
    setDest(hits[0]);
    setPicked(hits.slice(0, 8));
    goTo(center.latitude, center.longitude, preset ? 0.2 : 0.06);
    setStatus(t.foundIn(hits.length, q));
    setMenuOpen(true);
    setDock("search");
  };

  const savePlace = (kind: "home" | "work") => {
    const place = { label: kind, ...coord };
    if (kind === "home") setHome(place);
    else setWork(place);
    Alert.alert(kind === "home" ? t.savedHome : t.savedWork, t.savedPlaceBody);
  };

  const originCoord = (): Coord => {
    if (!origin || origin.kind === "gps") return coordRef.current;
    return { latitude: origin.latitude, longitude: origin.longitude };
  };

  const startInAppRoute = (to: { lat: number; lng: number; name?: string | null }) =>
    fetchAndApplyRoute(originCoord(), to);

  const previewStation = (s: Station) => {
    setChoosing(false);
    setDest(s);
    setStatus(t.destStatus(s.name || s.id));
    setDock(null);
    setMenuOpen(false);
    setTripOpen(false);
    setChatOpen(false);
    followLockRef.current = false;
    void fetchAndApplyRoute(originCoord(), s, { preview: true });
  };

  const previewTrip = () => {
    if (!dest) {
      Alert.alert(t.chooseDest, t.typeDest);
      return;
    }
    fetchAndApplyRoute(originCoord(), dest, { preview: true });
  };

  const applySuggest = (item: Suggest) => {
    if (activeField === "origin") {
      setOrigin({
        latitude: item.latitude,
        longitude: item.longitude,
        label: item.label,
        kind: "map",
      });
      setOriginQuery(item.label);
      setActiveField("dest");
      if (dest) {
        fetchAndApplyRoute(
          { latitude: item.latitude, longitude: item.longitude },
          dest,
          { preview: true }
        );
      }
    } else {
      const s: Station = {
        id: item.id,
        name: item.label,
        lat: item.latitude,
        lng: item.longitude,
        city: item.sub,
        source: "search",
      };
      setDest(s);
      setDestQuery(item.label);
      fetchAndApplyRoute(originCoord(), s, { preview: true });
    }
    setSuggests([]);
  };

  const swapTrip = () => {
    const prevO = origin;
    const prevD = dest;
    const oq = originQuery;
    setOriginQuery(destQuery);
    setDestQuery(oq);
    if (prevD) {
      setOrigin({
        latitude: prevD.lat,
        longitude: prevD.lng,
        label: prevD.name || prevD.id,
        kind: "station",
      });
    }
    if (prevO) {
      setDest({
        id: "swap-dest",
        name: prevO.label,
        lat: prevO.latitude,
        lng: prevO.longitude,
        city: null,
        source: "search",
      });
    }
    if (prevO && prevD) {
      fetchAndApplyRoute(
        { latitude: prevD.lat, longitude: prevD.lng },
        { lat: prevO.latitude, lng: prevO.longitude, name: prevO.label },
        { preview: true }
      );
    }
  };

  const openChat = () => {
    setMenuOpen(false);
    setDock(null);
    setTripOpen(false);
    setChatOpen(true);
  };

  const stationFromHit = (hit: ChatHit): Station => ({
    id: hit.id,
    name: hit.name,
    lat: hit.lat,
    lng: hit.lng,
    city: hit.city,
    source: hit.source,
  });

  const pickFromChat = (hit: ChatHit) => {
    previewStation(stationFromHit(hit));
  };

  const navFromChat = (hit: ChatHit) => {
    const station = stationFromHit(hit);
    setDest(station);
    setChatOpen(false);
    setMenuOpen(false);
    setDock(null);
    startInAppRoute(station);
  };

  const placeFromMap = (lat: number, lng: number): Station => ({
    id: `map-${lat.toFixed(5)}-${lng.toFixed(5)}`,
    name: t.pickedOnMap,
    lat,
    lng,
    city: null,
    source: "map",
  });

  const search = () => {
    const rangeKm = SAFETY * ((CAPACITY_KWH * 1000 * battery) / 100) / WH_PER_KM;
    const from = focus ?? coord;
    const preset = CITY_PRESETS.find((p) => p.id === regionId);
    const pool = preset?.city ? ALL.filter((s) => s.city === preset.city) : ALL;
    const ranked = pool
      .map((s) => ({
        s,
        d: haversineKm(from.latitude, from.longitude, s.lat, s.lng),
      }))
      .filter((x) => x.d <= Math.min(rangeKm, 40))
      .sort((a, b) => a.d - b.d)
      .slice(0, 5);
    setPicked([]);
    setChip("charger");
    setDest(null);
    setPreviewing(false);
    setRouteLine([]);
    setRouteMeta(null);
    if (ranked.length === 0) {
      setChoosing(false);
      setShortlist([]);
      setDock(null);
      setMenuOpen(false);
      Alert.alert(t.noStationTitle, t.noStationBody(battery, rangeKm.toFixed(0)));
      setStatus(t.noStationStatus);
      return;
    }
    const five = ranked.map((x) => x.s);
    setShortlist(five);
    setChoosing(true);
    setSearchHits(five);
    setMenuOpen(false);
    setDock("search");
    const lat = five.reduce((sum, s) => sum + s.lat, 0) / five.length;
    const lng = five.reduce((sum, s) => sum + s.lng, 0) / five.length;
    const span = five.reduce(
      (max, s) => Math.max(max, Math.abs(s.lat - lat), Math.abs(s.lng - lng)),
      0.02
    );
    goTo(lat, lng, Math.min(0.09, Math.max(0.04, span * 2.8)));
    setStatus(t.filterChoices(five.length));
  };

  const undoFilter = () => {
    if (!shortlist.length) return;
    setChoosing(true);
    setDest(null);
    setPreviewing(false);
    setRouteLine([]);
    setRouteMeta(null);
    setSnapPos(null);
    setSearchHits(shortlist);
    setDock("search");
    setMenuOpen(false);
    setTripOpen(false);
    setChatOpen(false);
    const lat = shortlist.reduce((sum, s) => sum + s.lat, 0) / shortlist.length;
    const lng = shortlist.reduce((sum, s) => sum + s.lng, 0) / shortlist.length;
    goTo(lat, lng, 0.08);
    setStatus(t.filterChoices(shortlist.length));
  };

  const curStep = navSteps[stepIndex];
  const nextStep = navSteps[stepIndex + 1];
  const curTitle = curStep
    ? maneuverTitle(
        lang,
        curStep.type,
        curStep.modifier,
        curStep.road,
        t.road,
        t.arrived,
        t.continueStraight
      )
    : t.continueStraight;
  const nextTitle = nextStep
    ? maneuverTitle(
        lang,
        nextStep.type,
        nextStep.modifier,
        nextStep.road,
        t.road,
        t.arrived,
        t.continueStraight
      )
    : null;
  const distToTurnM = curStep ? Math.max(0, curStep.cumEndM - (totalMRef.current - remainM)) : remainM;
  const distToTurn =
    distToTurnM >= 1000 ? `${(distToTurnM / 1000).toFixed(1)} ${t.kmLabel}` : `${Math.round(distToTurnM)} m`;
  const routeParts =
    navigating && routeLine.length > 1 ? splitRoute(routeLine, snapPos || coord) : null;
  const originText = !origin || origin.kind === "gps" ? t.yourLocation : origin.label;

  if (tab === "settings") {
    return (
      <View style={styles.root}>
        <Text style={[styles.logo, { paddingTop: 56, paddingHorizontal: 16 }]}>{t.settings}</Text>
        <Text style={styles.settingsBody}>{t.accountDemo}</Text>
        <Text style={styles.settingsBody}>{gpsError || status || t.locatingStatus}</Text>
        <View style={{ paddingHorizontal: 16 }}>
          <DarkModeRow compact />
        </View>
        <Pressable style={styles.go} onPress={onLogout}>
          <Text style={styles.goText}>{t.logout}</Text>
        </Pressable>
        <Pressable style={styles.ghost} onPress={() => setTab("explore")}>
          <Text style={styles.darkLabel}>{t.backToMap}</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.mapWrap}>
        <MapView
          ref={mapRef}
          style={styles.map}
          provider={Platform.OS === "android" ? PROVIDER_GOOGLE : undefined}
          mapType={Platform.OS === "ios" ? "mutedStandard" : "standard"}
          customMapStyle={
            Platform.OS === "android" ? (dark || navigating ? DARK_MAP : LIGHT_MAP) : undefined
          }
          userInterfaceStyle={dark || navigating ? "dark" : "light"}
          showsUserLocation={false}
          showsMyLocationButton={false}
          showsPointsOfInterests={false}
          showsTraffic={false}
          showsCompass
          rotateEnabled
          pitchEnabled
          onPanDrag={() => {
            followLockRef.current = false;
            navCamLockRef.current = false;
          }}
          onLongPress={(e) => {
            const { latitude, longitude } = e.nativeEvent.coordinate;
            if (pickMode === "origin") {
              setOrigin({ latitude, longitude, label: t.pickedOnMap, kind: "map" });
              setPickMode(null);
              setTripOpen(true);
              setStatus(`${t.originLabel}：${t.pickedOnMap}`);
              return;
            }
            if (pickMode === "dest") {
              const s = placeFromMap(latitude, longitude);
              setDest(s);
              setPickMode(null);
              setTripOpen(true);
              setStatus(t.destStatus(s.name || s.id));
            }
          }}
          initialRegion={{
            ...FALLBACK,
            latitudeDelta: 0.08,
            longitudeDelta: 0.08,
          }}
          onRegionChange={() => syncMapHeading()}
          onRegionChangeComplete={(next) => {
            setView(next);
            syncMapHeading(true);
          }}
        >
          <Marker
            coordinate={snapPos || coord}
            title={t.currentLocation}
            anchor={{ x: 0.5, y: 0.5 }}
            tracksViewChanges
            zIndex={999}
          >
            <View style={{ width: 72, height: 72, alignItems: "center", justifyContent: "center", transform: [{ rotate: `${((navigating ? driveHeading : heading) - mapHeading + 360) % 360}deg` }] }}>
              <HeadingArrow navigating={navigating} />
            </View>
          </Marker>
          {!navigating && home ? (
            <Marker coordinate={home} title={t.home} pinColor="green" />
          ) : null}
          {!navigating && work ? (
            <Marker coordinate={work} title={t.work} pinColor="purple" />
          ) : null}
          {origin && origin.kind !== "gps" ? (
            <Marker
              coordinate={{ latitude: origin.latitude, longitude: origin.longitude }}
              title={origin.label}
              pinColor="navy"
            />
          ) : null}
          {routeParts ? (
            <>
              {routeParts.done.length > 1 ? (
                <Polyline coordinates={routeParts.done} strokeColor="#94A3B8" strokeWidth={6} />
              ) : null}
              {routeParts.remain.length > 1 ? (
                <Polyline coordinates={routeParts.remain} strokeColor="#4FC3F7" strokeWidth={8} />
              ) : null}
            </>
          ) : routeLine.length > 1 ? (
            <Polyline
              coordinates={routeLine}
              strokeColor="#16a34a"
              strokeWidth={previewing ? 6 : 5}
            />
          ) : null}
          {dest && (navigating || previewing) ? (
            <Marker
              coordinate={{ latitude: dest.lat, longitude: dest.lng }}
              title={dest.name || dest.id}
              pinColor="green"
            />
          ) : null}
          {mapMarks.bubbles.map((c) => (
            <Marker
              key={`c-${c.id}`}
              coordinate={{ latitude: c.lat, longitude: c.lng }}
              anchor={{ x: 0.5, y: 0.5 }}
              tracksViewChanges={false}
              onPress={() => goTo(c.lat, c.lng, Math.max(view.latitudeDelta * 0.42, 0.05))}
            >
              <View
                style={[
                  styles.cluster,
                  c.count >= 50 ? styles.clusterLg : c.count >= 10 ? styles.clusterMd : null,
                ]}
              >
                <Text style={styles.clusterNum}>{c.count}</Text>
              </View>
            </Marker>
          ))}
          {mapMarks.pins.map((s) => {
            const highlight = (choosing && shortlist.some((p) => p.id === s.id)) || dest?.id === s.id;
            return (
              <Marker
                key={`${s.id}-${highlight ? "on" : "off"}`}
                coordinate={{ latitude: s.lat, longitude: s.lng }}
                title={s.name || s.id}
                description={
                  dest?.id === s.id
                    ? t.tapAgainToUnlock
                    : pickMode === "origin"
                      ? t.tapMapForStart
                      : t.tapToSetDest
                }
                anchor={{ x: 0.5, y: 1 }}
                tracksViewChanges={false}
                onPress={() => {
                  if (pickMode === "origin") {
                    setOrigin({
                      latitude: s.lat,
                      longitude: s.lng,
                      label: s.name || s.id,
                      kind: "station",
                    });
                    setPickMode(null);
                    setTripOpen(true);
                    setStatus(`${t.originLabel}：${s.name || s.id}`);
                    return;
                  }
                  if (dest?.id === s.id) {
                    unlockStation(true);
                    return;
                  }
                  if (pickMode === "dest") {
                    setDest(s);
                    setStatus(t.destStatus(s.name || s.id));
                    setPickMode(null);
                    setTripOpen(true);
                    void fetchAndApplyRoute(originCoord(), s, { preview: true });
                  } else {
                    previewStation(s);
                  }
                }}
              >
                <View style={styles.pinWrap}>
                  <View style={[styles.pinHead, highlight && styles.pinHeadOn]}>
                    <Text style={styles.pinBolt}>⚡</Text>
                  </View>
                  <View style={[styles.pinTail, highlight && styles.pinTailOn]} />
                </View>
              </Marker>
            );
          })}
        </MapView>

        {navigating ? (
          <>
            <View style={styles.navBanner}>
              <View style={styles.navBannerRow}>
                <Text style={styles.navArrow}>{maneuverArrow(curStep?.type || "", curStep?.modifier || "")}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.navDist}>{distToTurn}</Text>
                  <Text style={styles.navRoad} numberOfLines={2}>
                    {curTitle}
                  </Text>
                </View>
              </View>
              {nextTitle ? (
                <View style={styles.thenRow}>
                  <Text style={styles.thenTxt}>
                    {t.then} {maneuverArrow(nextStep?.type || "", nextStep?.modifier || "")}
                  </Text>
                </View>
              ) : null}
            </View>

            <View style={styles.navSide}>
              <Pressable
                style={styles.navSideBtn}
                onPress={() => {
                  setVoiceOn((on) => {
                    const next = !on;
                    voiceOnRef.current = next;
                    if (!next) void Speech.stop();
                    return next;
                  });
                }}
              >
                <Text style={styles.navSideTxt}>{voiceOn ? "🔊" : "🔇"}</Text>
              </Pressable>
              <Pressable
                style={styles.navSideBtn}
                onPress={() => {
                  navCamLockRef.current = true;
                  followUser(snapPos || coordRef.current, true, driveBearingRef.current || headingLiveRef.current);
                }}
              >
                <Text style={styles.navSideTxt}>🧭</Text>
              </Pressable>
            </View>

            <View style={styles.navBar}>
              <View>
                <Text style={styles.etaMin}>
                  {formatDriveTime(remainS / 60, lang)}
                </Text>
                <Text style={styles.etaSub}>
                  {(remainM / 1000).toFixed(1)} {t.kmLabel} · {formatArrival(remainS, lang)}
                </Text>
              </View>
              <Pressable style={styles.endBtn} onPress={endNavigation}>
                <Text style={styles.endTxt}>{t.endNav}</Text>
              </Pressable>
            </View>
          </>
        ) : (
          <>
            <View style={styles.topBar}>
              <Pressable style={styles.roundBtn} onPress={() => setDock("menu")}>
                <Text style={styles.roundIcon}>☰</Text>
              </Pressable>
              <View style={{ flex: 1 }} />
              <Pressable style={styles.roundBtn} onPress={() => setDock("search")}>
                <Text style={styles.roundIcon}>⌕</Text>
              </Pressable>
              <Pressable style={styles.roundBtn} onPress={() => setDock("filter")}>
                <Text style={styles.roundIcon}>▾</Text>
              </Pressable>
            </View>
            {pickMode ? (
              <Text style={styles.pickBanner}>
                {pickMode === "origin" ? t.tapMapForStart : t.tapMapForDest}
              </Text>
            ) : null}
            <Pressable
              style={styles.locateBtn}
              onPress={() => {
                followLockRef.current = true;
                centerOnMe(coordRef.current, ME_DELTA);
                void locate(false);
              }}
            >
              <Text style={styles.locateIcon}>⌖</Text>
            </Pressable>
            {!dock && !tripOpen && !chatOpen && !previewing ? (
              <View style={styles.tabBar}>
                <Pressable style={styles.tabItem} onPress={() => setDock("search")}>
                  <Text style={styles.tabIcon}>⚡</Text>
                  <Text style={styles.tabLabel}>{t.findStations}</Text>
                </Pressable>
                <Pressable style={styles.tabItem} onPress={() => setDock("help")}>
                  <Text style={styles.tabIcon}>i</Text>
                  <Text style={styles.tabLabel}>{t.help}</Text>
                </Pressable>
              </View>
            ) : null}
            <CompassRose heading={heading} mapHeading={mapHeading} lang={lang} onReset={resetNorth} />
          </>
        )}
        {navigating ? (
          <CompassRose heading={heading} mapHeading={mapHeading} lang={lang} navigating onReset={resetNorth} />
        ) : null}
      </View>

      {!navigating && !menuOpen && !chatOpen && previewing && dest ? (
        <View style={styles.previewBar}>
          <View style={styles.previewTop}>
            <View style={{ flex: 1 }}>
              <Text style={styles.etaMin}>{routeMeta ? routeMeta.min : t.previewTrip}</Text>
              <Text style={styles.previewSub} numberOfLines={2}>
                {originText} → {dest.name || t.chargerDefault}
                {routeMeta ? ` · ${routeMeta.km} km` : ""}
              </Text>
            </View>
            <Pressable onPress={() => unlockStation()} hitSlop={8}>
              <Text style={styles.previewClose}>{t.closePreview}</Text>
            </Pressable>
          </View>
          {shortlist.some((p) => p.id === dest.id) ? (
            <Pressable style={styles.previewBack} onPress={undoFilter}>
              <Text style={styles.previewBackTxt}>{t.undoStep}</Text>
            </Pressable>
          ) : null}
          <Pressable
            style={styles.previewGo}
            onPress={() => startInAppRoute(dest)}
            disabled={routing}
          >
            <Text style={styles.goText}>{routing ? t.routing : t.startFromHere}</Text>
          </Pressable>
        </View>
      ) : null}

      {!navigating && !dock && !menuOpen && !chatOpen && !tripOpen && !previewing && dest ? (
        <View style={styles.slimNav}>
          <Pressable
            style={styles.slimMain}
            onPress={() => startInAppRoute(dest)}
            disabled={routing}
          >
            <Text style={styles.goText} numberOfLines={1}>
              {routing ? t.routing : t.slimNav(dest.name || t.chargerDefault)}
            </Text>
          </Pressable>
          <Pressable style={styles.slimX} onPress={() => unlockStation()} hitSlop={8}>
            <Text style={styles.slimXTxt}>×</Text>
          </Pressable>
        </View>
      ) : null}

      {!navigating && !tripOpen && dock === "menu" ? (
        <View style={styles.drawerWrap}>
          <Pressable style={styles.drawerBackdrop} onPress={() => { setDock(null); setMenuOpen(false); }} />
          <View style={styles.drawer}>
            <View style={styles.drawerHead}>
              <View style={styles.avatar}>
                <Text style={styles.avatarTxt}>☺</Text>
              </View>
              <Text style={styles.drawerMail}>{t.menuAccount}</Text>
            </View>
            <DarkModeRow />
            {[
              { label: t.planTrip, onPress: () => {
                setDock(null);
                setMenuOpen(false);
                setTripOpen(true);
                setActiveField("origin");
                setOrigin({ ...coord, label: t.yourLocation, kind: "gps" });
                setOriginQuery(t.yourLocation);
                setDestQuery(dest?.name || "");
                setSuggests([]);
              } },
              { label: t.askCharger, onPress: openChat },
              { label: t.home, onPress: () => onChip("home") },
              { label: t.work, onPress: () => onChip("work") },
              { label: t.charger, onPress: () => { onChip("charger"); setDock("search"); } },
              { label: t.settingsLogout, onPress: () => setTab("settings") },
            ].map((row) => (
              <Pressable key={row.label} style={styles.menuRow} onPress={row.onPress}>
                <Text style={styles.menuRowTxt}>{row.label}</Text>
                <Text style={styles.chevron}>›</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {!navigating && !tripOpen && (dock === "search" || dock === "filter" || dock === "help") ? (
        <View style={styles.sheet}>
          <View style={styles.sheetHead}>
            <Pressable onPress={() => { setDock(null); setMenuOpen(false); }}>
              <Text style={styles.sheetX}>×</Text>
            </Pressable>
            <Text style={styles.sheetTitle}>
              {dock === "search" ? t.searchGo : dock === "filter" ? t.filterTitle : t.help}
            </Text>
            {dock === "filter" ? (
              <Pressable
                onPress={() => {
                  setBattery(80);
                  applyRegion("nearby");
                  setQuery("");
                  setSearchHits([]);
                }}
              >
                <Text style={styles.clearTxt}>{t.clearAll}</Text>
              </Pressable>
            ) : (
              <View style={{ width: 64 }} />
            )}
          </View>
          {dock === "help" ? (
            <View style={styles.panel}>
              <Text style={styles.sheetBody}>{t.helpBody}</Text>
              <Pressable style={styles.go} onPress={openChat}>
                <Text style={styles.goText}>{t.askCharger}</Text>
              </Pressable>
              <View style={styles.langRow}>
                <Text style={styles.muted}>{t.language}</Text>
                <Chip label={t.chinese} active={lang === "zh"} onPress={() => setLang("zh")} />
                <Chip label={t.english} active={lang === "en"} onPress={() => setLang("en")} />
              </View>
              <DarkModeRow compact />
            </View>
          ) : null}
          {dock === "search" ? (
            <ScrollView keyboardShouldPersistTaps="handled">
              <View style={styles.searchBox}>
                <TextInput
                  style={styles.searchField}
                  placeholder={t.searchPlaceholder}
                  placeholderTextColor={ink.muted}
                  value={query}
                  onChangeText={setQuery}
                  returnKeyType="search"
                  onSubmitEditing={runPlaceSearch}
                />
                <Pressable onPress={runPlaceSearch}>
                  <Text style={styles.searchIcon}>⌕</Text>
                </Pressable>
              </View>
              <Text style={styles.sectionTitle}>{choosing ? t.pickOne : t.nearbySpots}</Text>
              {(searchHits.length ? searchHits : shown).slice(0, 8).map((s) => {
                const km = haversineKm(coord.latitude, coord.longitude, s.lat, s.lng);
                return (
                  <Pressable
                    key={s.id}
                    style={[styles.stationCard, dest?.id === s.id && styles.stationOn]}
                    onPress={() => previewStation(s)}
                  >
                    <Text style={styles.bolt}>⚡</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.hitName} numberOfLines={1}>{s.name || s.id}</Text>
                      <Text style={styles.hint}>{s.city || t.chargerDefault}</Text>
                    </View>
                    <Text style={styles.kmTxt}>~{km < 10 ? km.toFixed(1) : km.toFixed(0)} km</Text>
                  </Pressable>
                );
              })}
              {dest ? (
                <Pressable style={styles.applyBtn} onPress={() => startInAppRoute(dest)} disabled={routing}>
                  <Text style={styles.goText}>{routing ? t.routingLong : t.navTo(dest.name || t.chargerDefault)}</Text>
                </Pressable>
              ) : null}
            </ScrollView>
          ) : null}
          {dock === "filter" ? (
            <ScrollView keyboardShouldPersistTaps="handled" scrollEnabled={menuScroll}>
              <View style={styles.filterCard}>
                <Text style={styles.sectionTitle}>{t.batteryLeft}</Text>
                <Text style={styles.battery}>{battery}%</Text>
                <BatterySlider
                  value={battery}
                  onChange={setBattery}
                  onDragStart={() => setMenuScroll(false)}
                  onDragEnd={() => setMenuScroll(true)}
                />
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
                  {CITY_PRESETS.map((p) => (
                    <Chip
                      key={p.id}
                      label={p.id === "nearby" ? t.regionNearby : p.keys[0]}
                      active={regionId === p.id}
                      onPress={() => applyRegion(p.id)}
                    />
                  ))}
                </ScrollView>
                <View style={styles.langRow}>
                  <Chip label={t.charger} active={chip === "charger"} onPress={() => onChip("charger")} />
                  <Chip label={t.home} active={chip === "home"} onPress={() => onChip("home")} />
                  <Chip label={t.work} active={chip === "work"} onPress={() => onChip("work")} />
                </View>
              </View>
              <Pressable
                style={styles.applyBtn}
                onPress={() => {
                  search();
                }}
              >
                <Text style={styles.goText}>{t.applyFilter}</Text>
              </Pressable>
            </ScrollView>
          ) : null}
        </View>
      ) : null}

      {!navigating && tripOpen ? (
        <View style={styles.tripCard} pointerEvents="box-none">
          <View style={styles.tripBox}>
            <TextInput
              style={styles.tripInput}
              placeholder={t.typeStart}
              placeholderTextColor={ink.muted}
              value={originQuery}
              onFocus={() => setActiveField("origin")}
              onChangeText={(txt) => {
                setOriginQuery(txt);
                setActiveField("origin");
              }}
            />
            <View style={styles.tripDivider} />
            <TextInput
              style={styles.tripInput}
              placeholder={t.typeDest}
              placeholderTextColor={ink.muted}
              value={destQuery}
              onFocus={() => setActiveField("dest")}
              onChangeText={(txt) => {
                setDestQuery(txt);
                setActiveField("dest");
              }}
            />
            <View style={styles.tripActions}>
              <Pressable onPress={swapTrip}>
                <Text style={styles.sheetClose}>{t.swap}</Text>
              </Pressable>
              <Pressable
                onPress={() => {
                  setTripOpen(false);
                  setSuggests([]);
                  setPickMode(null);
                }}
              >
                <Text style={styles.sheetClose}>{t.closePreview}</Text>
              </Pressable>
            </View>
          </View>
          {activeField === "origin" ? (
            <View style={styles.suggestList}>
              <Pressable
                style={styles.hitRow}
                onPress={() => {
                  setOrigin({ ...coord, label: t.yourLocation, kind: "gps" });
                  setOriginQuery(t.yourLocation);
                  setActiveField("dest");
                  setSuggests([]);
                  if (dest) fetchAndApplyRoute(coord, dest, { preview: true });
                }}
              >
                <Text style={styles.hitName}>{t.yourLocation}</Text>
              </Pressable>
              {home ? (
                <Pressable
                  style={styles.hitRow}
                  onPress={() => {
                    setOrigin({ ...home, label: t.home, kind: "home" });
                    setOriginQuery(t.home);
                    setActiveField("dest");
                    setSuggests([]);
                    if (dest) fetchAndApplyRoute(home, dest, { preview: true });
                  }}
                >
                  <Text style={styles.hitName}>{t.home}</Text>
                </Pressable>
              ) : null}
              {work ? (
                <Pressable
                  style={styles.hitRow}
                  onPress={() => {
                    setOrigin({ ...work, label: t.work, kind: "work" });
                    setOriginQuery(t.work);
                    setActiveField("dest");
                    setSuggests([]);
                    if (dest) fetchAndApplyRoute(work, dest, { preview: true });
                  }}
                >
                  <Text style={styles.hitName}>{t.work}</Text>
                </Pressable>
              ) : null}
            </View>
          ) : null}
          {suggests.length ? (
            <ScrollView style={styles.suggestScroll} keyboardShouldPersistTaps="handled">
              {suggests.map((item) => (
                <Pressable key={item.id} style={styles.hitRow} onPress={() => applySuggest(item)}>
                  <Text style={styles.hitName} numberOfLines={1}>
                    {item.label}
                  </Text>
                  {item.sub ? (
                    <Text style={styles.hint} numberOfLines={2}>
                      {item.sub}
                    </Text>
                  ) : null}
                </Pressable>
              ))}
            </ScrollView>
          ) : null}
        </View>
      ) : null}

      {!gpsReady ? <Text style={styles.loading}>{t.locating}</Text> : null}
      <ChatPanel
        open={chatOpen && !navigating}
        latitude={coord.latitude}
        longitude={coord.longitude}
        battery={battery}
        dest={
          dest
            ? {
                id: dest.id,
                name: dest.name,
                lat: dest.lat,
                lng: dest.lng,
                city: dest.city,
                source: dest.source,
              }
            : null
        }
        onClose={() => setChatOpen(false)}
        onPick={pickFromChat}
        onNavigate={navFromChat}
      />
    </View>
  );
}

function facingName(heading: number, lang: Lang) {
  const names =
    lang === "zh"
      ? ["北", "東北", "東", "東南", "南", "西南", "西", "西北"]
      : ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return names[Math.round(heading / 45) % 8];
}

function CompassRose({
  heading,
  mapHeading,
  lang,
  navigating = false,
  onReset,
}: {
  heading: number;
  mapHeading: number;
  lang: Lang;
  navigating?: boolean;
  onReset: () => void;
}) {
  const styles = useStyles();
  const upright = { transform: [{ rotate: `${mapHeading}deg` }] };
  return (
    <Pressable style={[styles.compass, navigating && styles.compassNav]} onPress={onReset}>
      <View style={styles.compassTick} />
      <View style={[styles.compassDial, { transform: [{ rotate: `${-mapHeading}deg` }] }]}>
        <Text style={[styles.compassLetter, styles.compassN, upright]}>N</Text>
        <Text style={[styles.compassLetter, styles.compassE, upright]}>E</Text>
        <Text style={[styles.compassLetter, styles.compassS, upright]}>S</Text>
        <Text style={[styles.compassLetter, styles.compassW, upright]}>W</Text>
      </View>
      <Text style={styles.compassFace}>{facingName(heading, lang)}</Text>
    </Pressable>
  );
}

function HeadingArrow({ navigating }: { navigating: boolean }) {
  const styles = useStyles();
  if (navigating) {
    return (
      <View style={styles.navPuck}>
        <View style={styles.navChevron} />
      </View>
    );
  }
  return (
    <View style={styles.meWrap}>
      <View style={styles.meBeam} />
      <View style={styles.meDot} />
    </View>
  );
}

function Chip({
  label,
  active,
  onPress,
  onLongPress,
}: {
  label: string;
  active?: boolean;
  onPress: () => void;
  onLongPress?: () => void;
}) {
  const { dark } = useTheme();
  const styles = useStyles();
  return (
    <Pressable
      onPress={onPress}
      onLongPress={onLongPress}
      style={[styles.chip, active && styles.chipOn]}
    >
      <Text style={{ color: active ? "#fff" : colors(dark).text, fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
}

function makeStyles(dark: boolean) {
  const p = colors(dark);
  return StyleSheet.create({
  root: { flex: 1, backgroundColor: p.bg },
  logo: { fontSize: 20, fontWeight: "700", color: "#16a34a" },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: 16,
  },
  search: {
    marginHorizontal: 16,
    borderRadius: 12,
    padding: 12,
    backgroundColor: "#111",
    color: "#fff",
  },
  searchBtn: {
    backgroundColor: "#16a34a",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  hitList: { marginBottom: 10, gap: 6 },
  hitRow: {
    backgroundColor: p.card,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  hitOn: { backgroundColor: p.cardOn },
  hitName: { fontWeight: "700", color: p.text },
  topFloat: {
    position: "absolute",
    top: 52,
    left: 16,
    right: 16,
    backgroundColor: p.float,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  pickHint: { color: p.greenText, fontSize: 12, marginTop: 4, fontWeight: "600" },
  planBtn: {
    backgroundColor: "#0f766e",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
    marginBottom: 12,
  },
  tripTitle: { fontWeight: "800", fontSize: 18, marginHorizontal: 16, marginBottom: 8, color: p.text },
  tripCard: {
    position: "absolute",
    top: 48,
    left: 12,
    right: 12,
    maxHeight: "58%",
  },
  tripBox: {
    backgroundColor: "#1f2937",
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 8,
  },
  tripInput: {
    color: "#fff",
    fontSize: 16,
    paddingVertical: 10,
  },
  tripDivider: { height: 1, backgroundColor: "#374151" },
  tripActions: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 6,
    paddingBottom: 4,
  },
  suggestList: {
    backgroundColor: p.sheet,
    borderRadius: 14,
    marginTop: 8,
    overflow: "hidden",
  },
  suggestScroll: {
    backgroundColor: p.sheet,
    borderRadius: 14,
    marginTop: 8,
    maxHeight: 220,
  },
  tripRow: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: "#111",
    borderRadius: 12,
    padding: 12,
  },
  placeRow: { flexDirection: "row", gap: 8, paddingHorizontal: 16, marginTop: 8 },
  placeChip: {
    flex: 1,
    backgroundColor: p.card,
    borderRadius: 16,
    paddingVertical: 12,
    alignItems: "center",
  },
  previewBar: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 24,
    backgroundColor: "#111827",
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
  },
  previewTop: { flexDirection: "row", alignItems: "flex-start", gap: 12 },
  previewClose: { color: "#86efac", fontWeight: "700", fontSize: 13, paddingTop: 6 },
  previewBack: {
    borderWidth: 1.5,
    borderColor: "#86efac",
    borderRadius: 20,
    paddingVertical: 10,
    alignItems: "center",
  },
  previewBackTxt: { color: "#86efac", fontWeight: "700" },
  previewGo: {
    backgroundColor: "#16a34a",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
  },
  previewSub: { color: "#d1d5db", marginTop: 4 },
  menuFab: {
    backgroundColor: "#16a34a",
    borderRadius: 22,
    paddingHorizontal: 18,
    paddingVertical: 14,
    elevation: 4,
  },
  menuFabTxt: { color: "#fff", fontWeight: "800", fontSize: 16 },
  chatFab: { backgroundColor: "#16a34a" },
  chatMenuBtn: {
    borderWidth: 1.5,
    borderColor: "#16a34a",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
    marginBottom: 12,
  },
  chatMenuTxt: { color: "#16a34a", fontWeight: "800" },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    maxHeight: "78%",
    backgroundColor: p.sheet,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingBottom: 20,
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 12,
  },
  sheetHandle: { alignItems: "center", paddingTop: 10, paddingBottom: 6 },
  handleBar: {
    width: 42,
    height: 5,
    borderRadius: 3,
    backgroundColor: p.handle,
    marginBottom: 6,
  },
  sheetClose: { color: "#16a34a", fontWeight: "700", fontSize: 13 },
  slimNav: {
    position: "absolute",
    left: 16,
    right: 16,
    bottom: 96,
    backgroundColor: "#16a34a",
    borderRadius: 22,
    paddingLeft: 16,
    paddingRight: 6,
    paddingVertical: 6,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  slimMain: { flex: 1, paddingVertical: 8 },
  slimX: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.18)",
  },
  slimXTxt: { color: "#fff", fontSize: 24, fontWeight: "600", lineHeight: 26 },
  chips: { flexDirection: "row", gap: 8, padding: 12, paddingHorizontal: 16 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: p.card,
  },
  chipOn: { backgroundColor: "#16a34a" },
  panel: { paddingHorizontal: 16, paddingBottom: 8 },
  panelKicker: { color: "#16a34a", fontSize: 12, fontWeight: "700" },
  panelTitle: { fontWeight: "700", marginBottom: 4, color: p.text },
  muted: { color: p.muted, fontSize: 12 },
  darkLabel: { color: p.text, fontWeight: "700", fontSize: 16 },
  battery: { fontSize: 22, fontWeight: "700", color: "#16a34a" },
  sliderHit: { height: 36, justifyContent: "center", marginTop: 6, marginBottom: 12 },
  sliderTrack: { height: 8, borderRadius: 4, backgroundColor: p.line, overflow: "hidden" },
  sliderFill: { height: 8, borderRadius: 4, backgroundColor: "#16a34a" },
  sliderThumb: {
    position: "absolute",
    width: 22,
    height: 22,
    marginLeft: -11,
    top: 7,
    borderRadius: 11,
    backgroundColor: "#16a34a",
    borderWidth: 2,
    borderColor: "#fff",
  },
  go: {
    backgroundColor: "#16a34a",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
  },
  navBtn: {
    backgroundColor: "#16a34a",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 8,
  },
  goText: { color: "#fff", fontWeight: "700" },
  hint: { fontSize: 11, color: p.muted, marginTop: 6 },
  langRow: { flexDirection: "row", alignItems: "center", gap: 8, marginVertical: 8 },
  routeBox: {
    marginTop: 10,
    padding: 10,
    backgroundColor: p.soft,
    borderRadius: 12,
  },
  routeTitle: { fontWeight: "700", color: p.greenText, marginBottom: 4 },
  mapWrap: { flex: 1 },
  map: { flex: 1 },
  floatCol: { position: "absolute", right: 12, bottom: 36, gap: 8, alignItems: "flex-end" },
  floatBtn: {
    backgroundColor: p.sheet,
    borderRadius: 14,
    padding: 10,
    elevation: 3,
    shadowOpacity: 0.15,
    shadowRadius: 6,
  },
  floatTxt: { fontSize: 11, textAlign: "center", color: p.text },
  loading: { position: "absolute", top: 56, alignSelf: "center", color: p.muted },
  settingsBody: { padding: 16, color: p.textBody },
  ghost: { alignItems: "center", padding: 16 },
  navBanner: {
    position: "absolute",
    top: 52,
    left: 12,
    right: 12,
  },
  navBannerRow: {
    backgroundColor: "#0f766e",
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  navArrow: { color: "#fff", fontSize: 42, fontWeight: "700", width: 48 },
  navDist: { color: "#d1fae5", fontSize: 13, fontWeight: "700" },
  navRoad: { color: "#fff", fontSize: 22, fontWeight: "800" },
  thenRow: {
    alignSelf: "flex-start",
    marginTop: 8,
    backgroundColor: "#0f766e",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  thenTxt: { color: "#fff", fontWeight: "700" },
  navSide: { position: "absolute", right: 12, bottom: 188, gap: 10 },
  navSideBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#111827",
    alignItems: "center",
    justifyContent: "center",
  },
  navSideTxt: { fontSize: 20 },
  navBar: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 24,
    backgroundColor: "#111827",
    borderRadius: 22,
    paddingHorizontal: 18,
    paddingVertical: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  etaMin: { color: "#86efac", fontSize: 28, fontWeight: "800" },
  etaSub: { color: "#d1d5db", marginTop: 2 },
  endBtn: {
    backgroundColor: "#ef4444",
    borderRadius: 22,
    paddingHorizontal: 22,
    paddingVertical: 12,
  },
  endTxt: { color: "#fff", fontWeight: "800", fontSize: 16 },
  meWrap: { width: 72, height: 72, alignItems: "center", justifyContent: "center" },
  meBeam: {
    position: "absolute",
    top: 0,
    width: 0,
    height: 0,
    borderLeftWidth: 22,
    borderRightWidth: 22,
    borderTopWidth: 46,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    borderTopColor: "rgba(66,133,244,0.55)",
  },
  meDot: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#1a73e8",
    borderWidth: 3,
    borderColor: "#fff",
  },
  navPuck: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 3,
  },
  navChevron: {
    width: 0,
    height: 0,
    marginBottom: 4,
    borderLeftWidth: 9,
    borderRightWidth: 9,
    borderBottomWidth: 20,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    borderBottomColor: "#1a73e8",
  },
  cluster: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#14b8c4",
    borderWidth: 3,
    borderColor: "#0f766e",
    alignItems: "center",
    justifyContent: "center",
  },
  clusterMd: { width: 48, height: 48, borderRadius: 24 },
  clusterLg: { width: 56, height: 56, borderRadius: 28 },
  clusterNum: { color: "#fff", fontWeight: "800", fontSize: 16 },
  pinWrap: { alignItems: "center" },
  pinHead: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#111827",
    alignItems: "center",
    justifyContent: "center",
  },
  pinHeadOn: { backgroundColor: "#0f766e" },
  pinBolt: { color: "#5eead4", fontSize: 14 },
  pinTail: {
    width: 0,
    height: 0,
    borderLeftWidth: 6,
    borderRightWidth: 6,
    borderTopWidth: 8,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    borderTopColor: "#111827",
    marginTop: -1,
  },
  pinTailOn: { borderTopColor: "#0f766e" },
  topBar: {
    position: "absolute",
    top: 54,
    left: 16,
    right: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  roundBtn: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#166534",
    alignItems: "center",
    justifyContent: "center",
    elevation: 4,
    shadowOpacity: 0.2,
    shadowRadius: 6,
  },
  roundIcon: { color: "#fff", fontSize: 24, fontWeight: "700" },
  pickBanner: {
    position: "absolute",
    top: 116,
    alignSelf: "center",
    backgroundColor: p.soft,
    color: p.greenText,
    overflow: "hidden",
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 6,
    fontWeight: "700",
  },
  compass: {
    position: "absolute",
    right: 14,
    bottom: 168,
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: p.sheet,
    alignItems: "center",
    justifyContent: "center",
    elevation: 3,
  },
  compassNav: { right: 4, bottom: 112 },
  compassDial: { position: "absolute", width: 64, height: 64 },
  compassLetter: { position: "absolute", fontSize: 11, fontWeight: "800", color: p.textBody },
  compassN: { top: 4, left: 26, color: "#16a34a" },
  compassE: { top: 24, right: 5 },
  compassS: { bottom: 4, left: 27 },
  compassW: { top: 24, left: 5 },
  compassTick: {
    position: "absolute",
    top: 3,
    width: 0,
    height: 0,
    borderLeftWidth: 4,
    borderRightWidth: 4,
    borderBottomWidth: 7,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    borderBottomColor: "#16a34a",
    zIndex: 2,
  },
  compassFace: { fontSize: 13, fontWeight: "800", color: p.text },
  locateBtn: {
    position: "absolute",
    right: 16,
    bottom: 108,
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: p.sheet,
    alignItems: "center",
    justifyContent: "center",
    elevation: 3,
  },
  locateIcon: { color: "#16a34a", fontSize: 22, fontWeight: "700" },
  tabBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 84,
    backgroundColor: p.sheet,
    borderTopWidth: 1,
    borderTopColor: p.line,
    flexDirection: "row",
    paddingTop: 8,
    paddingBottom: 18,
  },
  tabItem: { flex: 1, alignItems: "center", justifyContent: "center", gap: 2 },
  tabIcon: { color: "#166534", fontSize: 18, fontWeight: "800" },
  tabLabel: { color: "#166534", fontSize: 11, fontWeight: "700" },
  drawerWrap: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, flexDirection: "row" },
  drawerBackdrop: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.25)" },
  drawer: {
    width: "82%",
    backgroundColor: p.bg,
    paddingTop: 64,
    paddingHorizontal: 12,
  },
  drawerHead: {
    backgroundColor: p.sheet,
    borderRadius: 16,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: p.cardOn,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarTxt: { color: p.greenText, fontSize: 20 },
  drawerMail: { fontWeight: "700", color: p.text },
  menuRow: {
    backgroundColor: p.sheet,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 16,
    marginBottom: 8,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  menuRowTxt: { fontSize: 16, color: p.text },
  chevron: { color: "#9ca3af", fontSize: 22 },
  sheetHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  sheetX: { fontSize: 28, color: p.text, width: 32 },
  sheetTitle: { fontSize: 20, fontWeight: "800", color: p.text },
  clearTxt: { color: "#16a34a", fontWeight: "700", width: 64, textAlign: "right" },
  sheetBody: { color: p.textBody, fontSize: 15, lineHeight: 22, paddingHorizontal: 16, paddingVertical: 8 },
  searchBox: {
    marginHorizontal: 16,
    marginTop: 8,
    backgroundColor: p.card,
    borderRadius: 14,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
  },
  searchField: { flex: 1, paddingVertical: 12, fontSize: 16, color: p.text },
  searchIcon: { color: "#166534", fontSize: 22, fontWeight: "700" },
  sectionTitle: { fontWeight: "800", fontSize: 16, marginHorizontal: 16, marginTop: 16, marginBottom: 8, color: p.text },
  stationCard: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: p.card,
    borderRadius: 16,
    padding: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  stationOn: { backgroundColor: p.cardOn },
  bolt: { color: "#16a34a", fontSize: 18 },
  kmTxt: { color: "#16a34a", fontWeight: "700" },
  filterCard: {
    marginHorizontal: 16,
    marginTop: 8,
    backgroundColor: p.card,
    borderRadius: 16,
    paddingVertical: 8,
  },
  applyBtn: {
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 24,
    backgroundColor: "#16a34a",
    borderRadius: 24,
    paddingVertical: 14,
    alignItems: "center",
  },
  });
}
