import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import MapView, { Marker, Polyline, PROVIDER_GOOGLE } from "react-native-maps";
import * as Location from "expo-location";
import stations from "../assets/stations.json";
import { useI18n, type Lang } from "../i18n";

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

export default function MapScreen({ onLogout }: Props) {
  const { t, lang, setLang } = useI18n();
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
  const coordRef = useRef(FALLBACK);
  const magRef = useRef<{ remove: () => void } | null>(null);
  const magOkRef = useRef(false);
  const compassOkRef = useRef(false);
  const destRef = useRef<Station | null>(null);
  const routingRef = useRef(false);
  const lastRerouteRef = useRef(0);

  const [coord, setCoord] = useState(FALLBACK);
  const [heading, setHeading] = useState(0);
  const [gpsReady, setGpsReady] = useState(false);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [battery, setBattery] = useState(80);
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<Coord | null>(null);
  const [searchHits, setSearchHits] = useState<Station[]>([]);
  const [regionId, setRegionId] = useState("nearby");
  const [chip, setChip] = useState<"charger" | "home" | "work" | "food">("charger");
  const [tab, setTab] = useState<"explore" | "settings">("explore");
  const [home, setHome] = useState<SavedPlace | null>(null);
  const [work, setWork] = useState<SavedPlace | null>(null);
  const [picked, setPicked] = useState<Station[]>([]);
  const [dest, setDest] = useState<Station | null>(null);
  destRef.current = dest;
  const [status, setStatus] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [routeLine, setRouteLine] = useState<Coord[]>([]);
  const [routeMeta, setRouteMeta] = useState<{ km: string; min: string; steps: string[] } | null>(
    null
  );
  const [routing, setRouting] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const [navSteps, setNavSteps] = useState<NavStep[]>([]);
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

  const followUser = (pos: Coord, force = false) => {
    const now = Date.now();
    if (!force && now - lastCamRef.current < 180) return;
    lastCamRef.current = now;
    mapRef.current?.animateToRegion(
      {
        latitude: pos.latitude,
        longitude: pos.longitude,
        latitudeDelta: 0.0032,
        longitudeDelta: 0.0032,
      },
      350
    );
  };

  const applyHeading = (value: number | null | undefined) => {
    if (value == null || !Number.isFinite(value) || value < 0) return;
    const next = ((value % 360) + 360) % 360;
    const prev = headingLiveRef.current;
    const diff = Math.abs(next - prev);
    const delta = Math.min(diff, 360 - diff);
    if (delta < 1) return;
    headingLiveRef.current = next;
    setHeading(next);
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
        min: Math.max(1, Math.round(route.duration / 60)).toString(),
        steps: strSteps.slice(0, 12),
      });
      setMenuOpen(false);
      if (!opts?.preview) setTripOpen(false);
      const snap = nearestOnLine(line, from);
      const puck = snap.distM > 12 ? from : snap.point;
      setSnapPos(puck);
      if (!compassOkRef.current) applyHeading(snap.bearing);
      setStatus(t.inAppNav(Math.round(route.duration / 60), (route.distance / 1000).toFixed(1)));
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
        setPreviewing(false);
        setNavigating(true);
        followUser(puck, true);
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

  const updateProgress = (pos: Coord) => {
    const line = lineRef.current;
    const steps = stepsRef.current;
    if (line.length < 2) return;
    const snap = nearestOnLine(line, pos);
    const puck = snap.distM > 12 ? pos : snap.point;
    setSnapPos(puck);
    followUser(puck);
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
    goTo(next.latitude, next.longitude, 0.01);
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
    setNavigating(false);
    setPreviewing(false);
    setSnapPos(null);
    setRouteLine([]);
    goTo(coord.latitude, coord.longitude, 0.02);
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

  const displayPins = !navigating && (chip === "charger" || chip === "food") ? shown : [];

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
    if (near[0]) setDest(near[0]);
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
    const ranked = ALL.map((s) => ({
      s,
      d: haversineKm(coord.latitude, coord.longitude, s.lat, s.lng),
    }))
      .filter((x) => x.d <= Math.min(rangeKm, 40))
      .sort((a, b) => a.d - b.d)
      .slice(0, 5);
    setPicked(ranked.map((x) => x.s));
    setChip("charger");
    if (ranked.length === 0) {
      Alert.alert(t.noStationTitle, t.noStationBody(battery, rangeKm.toFixed(0)));
      setStatus(t.noStationStatus);
      return;
    }
    const best = ranked[0].s;
    setDest(best);
    setMenuOpen(true);
    const lines = ranked
      .map((x, i) => `${i + 1}. ${x.s.name || x.s.id}（${x.d.toFixed(1)} km）`)
      .join("\n");
    Alert.alert(t.recTitle(battery), t.recBody(rangeKm.toFixed(0), lines), [
      { text: t.viewMap },
      { text: t.startNav, onPress: () => startInAppRoute(best) },
    ]);
    setStatus(t.pickedStatus(best.name || best.id));
    goTo(best.lat, best.lng, 0.06);
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
        <Pressable style={styles.go} onPress={onLogout}>
          <Text style={styles.goText}>{t.logout}</Text>
        </Pressable>
        <Pressable style={styles.ghost} onPress={() => setTab("explore")}>
          <Text>{t.backToMap}</Text>
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
          customMapStyle={navigating ? DARK_MAP : []}
          userInterfaceStyle={navigating ? "dark" : "light"}
          showsUserLocation={false}
          showsMyLocationButton={false}
          showsCompass
          rotateEnabled
          pitchEnabled
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
        >
          <Marker
            coordinate={snapPos || coord}
            title={t.currentLocation}
            anchor={{ x: 0.5, y: 0.65 }}
            flat
            tracksViewChanges
            zIndex={999}
          >
            <View style={{ transform: [{ rotate: `${heading}deg` }] }}>
              <HeadingArrow />
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
              strokeColor={previewing ? "#2563eb" : "#16a34a"}
              strokeWidth={previewing ? 6 : 5}
            />
          ) : dest ? (
            <Polyline
              coordinates={[originCoord(), { latitude: dest.lat, longitude: dest.lng }]}
              strokeColor="#86efac"
              strokeWidth={3}
            />
          ) : null}
          {dest && (navigating || previewing) ? (
            <Marker
              coordinate={{ latitude: dest.lat, longitude: dest.lng }}
              title={dest.name || dest.id}
              pinColor="green"
            />
          ) : null}
          {displayPins.map((s) => {
            const highlight = dest?.id === s.id || picked.some((p) => p.id === s.id);
            return (
              <Marker
                key={s.id}
                coordinate={{ latitude: s.lat, longitude: s.lng }}
                title={s.name || s.id}
                description={pickMode === "origin" ? t.tapMapForStart : t.tapToSetDest}
                pinColor={highlight ? "green" : "orange"}
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
                  setDest(s);
                  setStatus(t.destStatus(s.name || s.id));
                  if (pickMode === "dest") {
                    setPickMode(null);
                    setTripOpen(true);
                  } else {
                    setMenuOpen(true);
                  }
                }}
              />
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
                onPress={() => followUser(snapPos || coord, true)}
              >
                <Text style={styles.navSideTxt}>🧭</Text>
              </Pressable>
            </View>

            <View style={styles.navBar}>
              <View>
                <Text style={styles.etaMin}>
                  {Math.max(1, Math.round(remainS / 60))} {t.minLabel}
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
            <View style={styles.topFloat}>
              <Text style={styles.logo}>MapExplore</Text>
              {pickMode ? (
                <Text style={styles.pickHint}>
                  {pickMode === "origin" ? t.tapMapForStart : t.tapMapForDest}
                </Text>
              ) : null}
            </View>
            <View style={styles.floatCol}>
              <Pressable style={styles.menuFab} onPress={() => setMenuOpen(true)}>
                <Text style={styles.menuFabTxt}>{t.features}</Text>
              </Pressable>
              <Pressable style={styles.floatBtn} onPress={() => locate(false)}>
                <Text style={styles.floatTxt}>{t.locate}</Text>
              </Pressable>
            </View>
          </>
        )}
      </View>

      {!navigating && !menuOpen && previewing && dest ? (
        <View style={styles.previewBar}>
          <View>
            <Text style={styles.etaMin}>
              {routeMeta ? `${routeMeta.min} ${t.minLabel}` : t.previewTrip}
            </Text>
            <Text style={styles.previewSub}>
              {originText} → {dest.name || t.chargerDefault}
              {routeMeta ? ` · ${routeMeta.km} km` : ""}
            </Text>
          </View>
          <View style={{ gap: 8 }}>
            <Pressable
              style={styles.navBtn}
              onPress={() => startInAppRoute(dest)}
              disabled={routing}
            >
              <Text style={styles.goText}>{t.startFromHere}</Text>
            </Pressable>
            <Pressable onPress={endNavigation}>
              <Text style={styles.sheetClose}>{t.closePreview}</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {!navigating && !menuOpen && !tripOpen && !previewing && dest ? (
        <Pressable
          style={styles.slimNav}
          onPress={() => startInAppRoute(dest)}
          disabled={routing}
        >
          <Text style={styles.goText}>
            {routing ? t.routing : t.slimNav(dest.name || t.chargerDefault)}
          </Text>
        </Pressable>
      ) : null}

      {!navigating && !tripOpen && menuOpen ? (
        <View style={styles.sheet}>
          <Pressable style={styles.sheetHandle} onPress={() => setMenuOpen(false)}>
            <View style={styles.handleBar} />
            <Text style={styles.sheetClose}>{t.collapseMenu}</Text>
          </Pressable>
          <ScrollView keyboardShouldPersistTaps="handled">
            <View style={styles.searchRow}>
              <TextInput
                style={[styles.search, { flex: 1, marginHorizontal: 0 }]}
                placeholder={t.searchPlaceholder}
                placeholderTextColor="#9ca3af"
                value={query}
                onChangeText={setQuery}
                returnKeyType="search"
                onSubmitEditing={runPlaceSearch}
              />
              <Pressable style={styles.searchBtn} onPress={runPlaceSearch}>
                <Text style={styles.goText}>{t.searchGo}</Text>
              </Pressable>
            </View>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chips}
            >
              {CITY_PRESETS.map((p) => {
                const label = p.id === "nearby" ? t.regionNearby : p.keys[0];
                return (
                  <Chip
                    key={p.id}
                    label={label}
                    active={regionId === p.id}
                    onPress={() => applyRegion(p.id)}
                  />
                );
              })}
            </ScrollView>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chips}
            >
              <Chip label={t.charger} active={chip === "charger"} onPress={() => onChip("charger")} />
              <Chip
                label={t.home}
                active={chip === "home"}
                onPress={() => onChip("home")}
                onLongPress={() => savePlace("home")}
              />
              <Chip
                label={t.work}
                active={chip === "work"}
                onPress={() => onChip("work")}
                onLongPress={() => savePlace("work")}
              />
              <Chip label={t.food} active={chip === "food"} onPress={() => onChip("food")} />
            </ScrollView>
            <View style={styles.panel}>
              <Pressable
                style={styles.planBtn}
                onPress={() => {
                  setMenuOpen(false);
                  setTripOpen(true);
                  setActiveField("origin");
                  setOrigin({ ...coord, label: t.yourLocation, kind: "gps" });
                  setOriginQuery(t.yourLocation);
                  setDestQuery(dest?.name || "");
                  setSuggests([]);
                }}
              >
                <Text style={styles.goText}>{t.planTrip}</Text>
              </Pressable>
              <Text style={styles.panelKicker}>{t.nearbyRec}</Text>
              <Text style={styles.panelTitle}>{t.smartSearch}</Text>
              <View style={styles.langRow}>
                <Text style={styles.muted}>{t.language}</Text>
                <Chip label={t.chinese} active={lang === "zh"} onPress={() => setLang("zh")} />
                <Chip label={t.english} active={lang === "en"} onPress={() => setLang("en")} />
              </View>
              <Text style={styles.muted}>{t.batteryLeft}</Text>
              <Text style={styles.battery}>{battery}%</Text>
              <View style={styles.battRow}>
                {[20, 50, 80, 100].map((v) => (
                  <Pressable
                    key={v}
                    style={[styles.battBtn, battery === v && styles.battOn]}
                    onPress={() => setBattery(v)}
                  >
                    <Text style={battery === v ? styles.battOnText : undefined}>{v}%</Text>
                  </Pressable>
                ))}
              </View>
              {searchHits.length ? (
                <View style={styles.hitList}>
                  {searchHits.slice(0, 8).map((s) => (
                    <Pressable
                      key={s.id}
                      style={[styles.hitRow, dest?.id === s.id && styles.hitOn]}
                      onPress={() => {
                        setDest(s);
                        goTo(s.lat, s.lng, 0.04);
                      }}
                    >
                      <Text style={styles.hitName} numberOfLines={1}>
                        {s.name || s.id}
                      </Text>
                      <Text style={styles.hint}>
                        {s.city} · {haversineKm(coord.latitude, coord.longitude, s.lat, s.lng).toFixed(0)} km
                      </Text>
                    </Pressable>
                  ))}
                </View>
              ) : null}
              <Pressable style={styles.go} onPress={search}>
                <Text style={styles.goText}>{t.startSearch}</Text>
              </Pressable>
              {dest ? (
                <Pressable
                  style={styles.navBtn}
                  onPress={() => startInAppRoute(dest)}
                  disabled={routing}
                >
                  <Text style={styles.goText}>
                    {routing ? t.routingLong : t.navTo(dest.name || t.chargerDefault)}
                  </Text>
                </Pressable>
              ) : (
                <Text style={styles.hint}>{t.pickPin}</Text>
              )}
              {routeMeta ? (
                <View style={styles.routeBox}>
                  <Text style={styles.routeTitle}>
                    {t.driveSummary(routeMeta.min, routeMeta.km)}
                  </Text>
                  {routeMeta.steps.map((s, i) => (
                    <Text key={i} style={styles.hint}>
                      {i + 1}. {s}
                    </Text>
                  ))}
                </View>
              ) : null}
              <Text style={styles.hint}>{gpsError || status || t.locatingStatus}</Text>
              <Pressable style={styles.ghost} onPress={() => setTab("settings")}>
                <Text>{t.settingsLogout}</Text>
              </Pressable>
            </View>
          </ScrollView>
        </View>
      ) : null}

      {!navigating && tripOpen ? (
        <View style={styles.tripCard} pointerEvents="box-none">
          <View style={styles.tripBox}>
            <TextInput
              style={styles.tripInput}
              placeholder={t.typeStart}
              placeholderTextColor="#9ca3af"
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
              placeholderTextColor="#9ca3af"
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
    </View>
  );
}

function HeadingArrow() {
  return (
    <View style={styles.gPuck}>
      <View style={styles.gHalo} />
      <View style={styles.gArrow} />
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
  return (
    <Pressable
      onPress={onPress}
      onLongPress={onLongPress}
      style={[styles.chip, active && styles.chipOn]}
    >
      <Text style={{ color: active ? "#fff" : "#111", fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#fff" },
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
    backgroundColor: "#f3f4f6",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  hitOn: { backgroundColor: "#dcfce7" },
  hitName: { fontWeight: "700", color: "#111" },
  topFloat: {
    position: "absolute",
    top: 52,
    left: 16,
    right: 16,
    backgroundColor: "rgba(255,255,255,0.92)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  pickHint: { color: "#166534", fontSize: 12, marginTop: 4, fontWeight: "600" },
  planBtn: {
    backgroundColor: "#0f766e",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
    marginBottom: 12,
  },
  tripTitle: { fontWeight: "800", fontSize: 18, marginHorizontal: 16, marginBottom: 8 },
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
    backgroundColor: "#fff",
    borderRadius: 14,
    marginTop: 8,
    overflow: "hidden",
  },
  suggestScroll: {
    backgroundColor: "#fff",
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
    backgroundColor: "#f3f4f6",
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
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  previewSub: { color: "#d1d5db", marginTop: 4, flexShrink: 1 },
  menuFab: {
    backgroundColor: "#16a34a",
    borderRadius: 22,
    paddingHorizontal: 18,
    paddingVertical: 14,
    elevation: 4,
  },
  menuFabTxt: { color: "#fff", fontWeight: "800", fontSize: 16 },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    maxHeight: "58%",
    backgroundColor: "#fff",
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
    backgroundColor: "#d1d5db",
    marginBottom: 6,
  },
  sheetClose: { color: "#16a34a", fontWeight: "700", fontSize: 13 },
  slimNav: {
    position: "absolute",
    left: 16,
    right: 16,
    bottom: 28,
    backgroundColor: "#2563eb",
    borderRadius: 22,
    paddingVertical: 14,
    alignItems: "center",
  },
  chips: { flexDirection: "row", gap: 8, padding: 12, paddingHorizontal: 16 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#f3f4f6",
  },
  chipOn: { backgroundColor: "#16a34a" },
  panel: { paddingHorizontal: 16, paddingBottom: 8 },
  panelKicker: { color: "#16a34a", fontSize: 12, fontWeight: "700" },
  panelTitle: { fontWeight: "700", marginBottom: 4 },
  muted: { color: "#6b7280", fontSize: 12 },
  battery: { fontSize: 22, fontWeight: "700", color: "#16a34a" },
  battRow: { flexDirection: "row", gap: 8, marginVertical: 8 },
  battBtn: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  battOn: { backgroundColor: "#16a34a", borderColor: "#16a34a" },
  battOnText: { color: "#fff", fontWeight: "700" },
  go: {
    backgroundColor: "#16a34a",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
  },
  navBtn: {
    backgroundColor: "#2563eb",
    borderRadius: 20,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 8,
  },
  goText: { color: "#fff", fontWeight: "700" },
  hint: { fontSize: 11, color: "#6b7280", marginTop: 6 },
  langRow: { flexDirection: "row", alignItems: "center", gap: 8, marginVertical: 8 },
  routeBox: {
    marginTop: 10,
    padding: 10,
    backgroundColor: "#f0fdf4",
    borderRadius: 12,
  },
  routeTitle: { fontWeight: "700", color: "#166534", marginBottom: 4 },
  mapWrap: { flex: 1 },
  map: { flex: 1 },
  floatCol: { position: "absolute", right: 12, bottom: 36, gap: 8, alignItems: "flex-end" },
  floatBtn: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 10,
    elevation: 3,
    shadowOpacity: 0.15,
    shadowRadius: 6,
  },
  floatTxt: { fontSize: 11, textAlign: "center", color: "#111" },
  loading: { position: "absolute", top: 56, alignSelf: "center", color: "#6b7280" },
  settingsBody: { padding: 16, color: "#374151" },
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
  navSide: { position: "absolute", right: 12, bottom: 130, gap: 10 },
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
  gPuck: {
    width: 72,
    height: 84,
    alignItems: "center",
    justifyContent: "center",
  },
  gHalo: {
    position: "absolute",
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "rgba(37,99,235,0.38)",
    bottom: 8,
  },
  gArrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 18,
    borderRightWidth: 18,
    borderBottomWidth: 52,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    borderBottomColor: "#fff",
    marginBottom: 10,
  },
});
