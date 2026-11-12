// Voice output for the assistant, plus the recording settings and silence detection
// used by ChatPanel. Replies are read by the phone's built-in voice: it starts at once
// and uses no Gemini quota. Set USE_GEMINI_VOICE to true for Gemini's more natural voice
// (WAV parts from the server, about 6 s slower; the phone voice still covers failures).

export const USE_GEMINI_VOICE = false;

import {
  createAudioPlayer,
  RecordingPresets,
  setAudioModeAsync,
  type AudioPlayer,
  type RecordingOptions,
} from "expo-audio";
import { File, Paths } from "expo-file-system";
import * as Speech from "expo-speech";
import * as api from "./api";
import type { Lang } from "./i18n";

const LISTEN_CUE = require("./assets/listen.wav");
// The server gives up on a reply part after 25 s; this also covers a stalled connection.
const SPEECH_DOWNLOAD_MS = 30000;

/** Mono AAC in an .m4a file: small uploads, and a format Gemini accepts. */
export const RECORDING: RecordingOptions = {
  ...RecordingPresets.HIGH_QUALITY,
  numberOfChannels: 1,
  bitRate: 64000,
  isMeteringEnabled: true,
};

export const playbackMode = () =>
  setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true, interruptionMode: "duckOthers" });

export const recordingMode = () =>
  setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true, interruptionMode: "duckOthers" });

/** Plays one file to the end. Resolves early if `cancel` is called. */
function playToEnd(source: string | number, maxMs: number) {
  let player: AudioPlayer | null = createAudioPlayer(source);
  let done: () => void = () => {};
  const finished = new Promise<void>((resolve) => {
    const timer = setTimeout(() => done(), maxMs);
    const sub = player!.addListener("playbackStatusUpdate", (s) => {
      if (s.didJustFinish) done();
    });
    done = () => {
      clearTimeout(timer);
      sub.remove();
      if (player) {
        player.pause();
        player.remove();
        player = null;
      }
      resolve();
    };
  });
  player.play();
  return { finished, cancel: () => done() };
}

/** Short two-tone chime: "I'm listening now". */
export async function playListenCue() {
  try {
    await playbackMode();
    await playToEnd(LISTEN_CUE, 1500).finished;
  } catch {
    // A missing chime must never block voice input.
  }
}

// A run of Chinese text, e.g. a station name inside an English reply ("市民大道-公中站").
const CJK = /[㐀-鿿豈-﫿]/;
const CJK_RUN = /([㐀-鿿豈-﫿][㐀-鿿豈-﫿\d\-－·（）()]*)/;

/** Speaks one utterance. Resolves true when it finished, false if it was stopped. */
function speakOnce(text: string, language: string): Promise<boolean> {
  return new Promise((resolve) => {
    Speech.speak(text, {
      language,
      onDone: () => resolve(true),
      onStopped: () => resolve(false),
      onError: () => resolve(true), // skip a part the voice can't say rather than hang
    });
  });
}

/**
 * The phone's own voice: instant, no network and no Gemini quota. In an English reply,
 * Chinese station names are read by the Chinese voice (the English one skips them).
 */
export async function sayLocally(text: string, lang: Lang): Promise<void> {
  const parts = lang === "zh" ? [text] : text.split(CJK_RUN).filter((p) => p.trim());
  for (const part of parts) {
    const zh = lang === "zh" || CJK.test(part);
    if (!(await speakOnce(part, zh ? "zh-TW" : "en-US"))) return;
  }
}

export class Speaker {
  private token = 0;
  private cancelCurrent: (() => void) | null = null;

  /** Speak the reply parts in order. Resolves true if it played to the end, false if stopped. */
  async play(parts: api.SpeechPart[], lang: Lang): Promise<boolean> {
    const my = ++this.token;
    await playbackMode();
    // Start every download now, so part 2 is ready by the time part 1 ends. A part that
    // isn't ready in time (or fails) is spoken with the phone's voice instead.
    const files = parts.map((part, i) => {
      const target = new File(Paths.cache, `reply-${Date.now()}-${i}.wav`);
      const download = File.downloadFileAsync(api.absoluteUrl(part.url), target, {
        headers: api.authHeaders(),
        idempotent: true,
      }).catch(() => null);
      return Promise.race([
        download,
        new Promise<null>((resolve) => setTimeout(() => resolve(null), SPEECH_DOWNLOAD_MS)),
      ]);
    });
    try {
      for (let i = 0; i < parts.length; i++) {
        const file = await files[i];
        if (my !== this.token) return false;
        if (file) {
          const playing = playToEnd(file.uri, 90000);
          this.cancelCurrent = playing.cancel;
          await playing.finished;
        } else {
          this.cancelCurrent = () => void Speech.stop();
          await sayLocally(parts[i].text, lang);
        }
        this.cancelCurrent = null;
        if (my !== this.token) return false;
      }
      return true;
    } finally {
      // Delete the downloaded audio once it has been played (or skipped).
      for (const pending of files) {
        pending.then((f) => {
          try {
            f?.delete();
          } catch {
            // already gone
          }
        });
      }
    }
  }

  /** Speak plain text with the phone's voice (stoppable like a reply). */
  async say(text: string, lang: Lang): Promise<boolean> {
    const my = ++this.token;
    await playbackMode();
    this.cancelCurrent = () => void Speech.stop();
    await sayLocally(text, lang);
    this.cancelCurrent = null;
    return my === this.token;
  }

  stop() {
    this.token++;
    this.cancelCurrent?.();
    this.cancelCurrent = null;
    void Speech.stop();
  }
}

/**
 * Decides when the speaker has finished talking, from the recorder's level meter (dB).
 * The first half second sets the background-noise floor; "speech" is anything clearly
 * louder. Recording stops after a pause, after a long silence, or at the time limit.
 */
export class SilenceDetector {
  private start = Date.now();
  private samples: number[] = [];
  private floor: number | null = null;
  private heard = false;
  private lastLoud = 0;

  constructor(private readonly followUp: boolean) {}

  /** "keep" recording, "send" it, or "drop" it (nothing was said in follow-up mode). */
  update(level: number | undefined): "keep" | "send" | "drop" {
    const now = Date.now();
    const elapsed = now - this.start;
    const db = typeof level === "number" && level > -150 ? level : null;
    if (elapsed < 500) {
      if (db !== null) this.samples.push(db);
      return "keep";
    }
    if (this.floor === null) {
      this.floor = this.samples.length ? Math.min(...this.samples) : -60;
    }
    if (db !== null && db > Math.max(this.floor + 12, -50)) {
      this.heard = true;
      this.lastLoud = now;
    }
    if (this.heard && now - this.lastLoud > 1400) return "send";
    if (elapsed > 15000) return "send";
    if (!this.heard && elapsed > (this.followUp ? 6000 : 8000)) {
      // Nothing detected. In follow-up mode that means "no more questions";
      // otherwise send anyway, in case the meter missed quiet speech.
      return this.followUp ? "drop" : "send";
    }
    return "keep";
  }
}
