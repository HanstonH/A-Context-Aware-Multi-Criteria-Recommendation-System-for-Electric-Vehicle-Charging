import type { Lang } from "./i18n";

export type VoiceStep = {
  road: string;
  type: string;
  modifier: string;
};

export type VoiceBand = "mid" | "near" | "now";

const GENERIC_ROADS = new Set(["", "道路", "road"]);

function cleanRoad(name: string) {
  const next = name.trim();
  return GENERIC_ROADS.has(next) ? "" : next;
}

function hasBridge(name: string) {
  return name.includes("橋");
}

export function voiceBand(distanceM: number): VoiceBand | null {
  if (distanceM <= 45) return "now";
  if (distanceM <= 180) return "near";
  if (distanceM <= 450) return "mid";
  return null;
}

function action(lang: Lang, step: VoiceStep, fromRoad: string) {
  const ty = step.type.toLowerCase();
  const m = step.modifier.toLowerCase();
  const onto = cleanRoad(step.road);
  const from = cleanRoad(fromRoad);
  const zh = lang === "zh";
  const side = m.includes("left") ? "left" : m.includes("right") ? "right" : "";
  const slight = m.includes("slight");
  const sharp = m.includes("sharp");
  const ontoBridge = hasBridge(onto);
  const fromBridge = hasBridge(from);

  if (ty === "arrive") return zh ? "抵達目的地" : "arrive";

  if (ontoBridge && !fromBridge) {
    if (zh) {
      if (side === "left" && !slight) return `左轉上${onto}`;
      if (side === "right" && !slight) return `右轉上${onto}`;
      if (side === "left") return `靠左上${onto}`;
      if (side === "right") return `靠右上${onto}`;
      return `上${onto}`;
    }
    if (side === "left" && slight) return `keep left onto ${onto}`;
    if (side === "right" && slight) return `keep right onto ${onto}`;
    if (side === "left") return `turn left onto ${onto}`;
    if (side === "right") return `turn right onto ${onto}`;
    return `get on ${onto}`;
  }

  if (fromBridge && !ontoBridge && ty !== "depart") {
    if (zh) {
      if (side === "left" && !slight) return "左轉下橋";
      if (side === "right" && !slight) return "右轉下橋";
      if (side === "left") return "靠左下橋";
      if (side === "right") return "靠右下橋";
      return "下橋";
    }
    if (side === "left" && slight) return "keep left off the bridge";
    if (side === "right" && slight) return "keep right off the bridge";
    if (side === "left") return "turn left off the bridge";
    if (side === "right") return "turn right off the bridge";
    return "leave the bridge";
  }

  if (ty === "on ramp") {
    if (zh) return side === "left" ? "靠左上匝道" : side === "right" ? "靠右上匝道" : "上匝道";
    return side === "left" ? "keep left onto the ramp" : side === "right" ? "keep right onto the ramp" : "take the ramp";
  }
  if (ty === "off ramp") {
    if (zh) return side === "left" ? "靠左下匝道" : side === "right" ? "靠右下匝道" : "下匝道";
    return side === "left" ? "keep left off the ramp" : side === "right" ? "keep right off the ramp" : "exit the ramp";
  }
  if (ty.includes("uturn") || m === "uturn") return zh ? "迴轉" : "make a U-turn";
  if (ty === "roundabout" || ty === "rotary") return zh ? "進入圓環" : "enter the roundabout";
  if (ty.includes("exit roundabout") || ty.includes("exit rotary")) return zh ? "駛出圓環" : "exit the roundabout";
  if (ty === "merge") {
    if (side === "left") return zh ? "靠左匯入" : "merge to the left";
    if (side === "right") return zh ? "靠右匯入" : "merge to the right";
    return zh ? "匯入車道" : "merge";
  }
  if (ty === "fork" || slight) {
    if (side === "left") return zh ? "靠左行駛" : "keep left";
    if (side === "right") return zh ? "靠右行駛" : "keep right";
  }
  if (sharp && side === "left") return zh ? "急左轉" : "turn sharp left";
  if (sharp && side === "right") return zh ? "急右轉" : "turn sharp right";
  if (side === "left" || ty.includes("left")) return zh ? "左轉" : "turn left";
  if (side === "right" || ty.includes("right")) return zh ? "右轉" : "turn right";
  return null;
}

export function voicePhrase(
  lang: Lang,
  step: VoiceStep,
  fromRoad: string,
  distanceM: number,
  band: VoiceBand
) {
  const act = action(lang, step, fromRoad);
  if (!act) return null;
  if (band === "now") {
    if (lang === "zh") return act === "抵達目的地" ? "已抵達目的地" : `現在請${act}`;
    return act === "arrive" ? "You have arrived" : `Now, ${act}`;
  }
  const onto = cleanRoad(step.road);
  const named = onto.length > 0 && act.includes(onto);
  const skipRoad =
    !onto ||
    named ||
    onto === cleanRoad(fromRoad) ||
    act.includes("橋") ||
    act.includes("匝道") ||
    act.includes("目的地") ||
    act === "arrive" ||
    step.type.toLowerCase() === "arrive";
  const roadBit = skipRoad ? "" : lang === "zh" ? `，進入${onto}` : ` onto ${onto}`;
  const shown = Math.max(50, Math.round(distanceM / 50) * 50);
  if (shown >= 1000) {
    const km = (shown / 1000).toFixed(shown % 1000 === 0 ? 0 : 1);
    return lang === "zh" ? `${km}公里後${act}${roadBit}` : `In ${km} kilometers, ${act}${roadBit}`;
  }
  return lang === "zh" ? `${shown}公尺後${act}${roadBit}` : `In ${shown} meters, ${act}${roadBit}`;
}
