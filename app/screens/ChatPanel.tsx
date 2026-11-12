import { useCallback, useEffect, useRef, useState, type ComponentRef } from "react";
import {
  requestRecordingPermissionsAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import {
  Alert,
  Keyboard,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as api from "../api";
import {
  cityLabel,
  haversineKm,
  replyTo,
  suggestionChips,
  welcomeText,
  type ChatHit,
  type ChatPlace,
} from "../chatbot";
import { useI18n } from "../i18n";
import {
  playListenCue,
  playbackMode,
  RECORDING,
  recordingMode,
  SilenceDetector,
  Speaker,
} from "../voice";

type Msg = {
  id: string;
  role: "user" | "bot";
  text: string;
  hits: ChatHit[];
  offline?: boolean; // answered by the on-phone chatbot because the server failed
  voice?: boolean; // spoken question
  note?: string; // small grey detail under the bubble (e.g. why voice failed)
};

export type VoicePhase = "idle" | "listening" | "thinking" | "speaking";
export type VoiceState = { phase: VoicePhase; followUp: boolean; caption: string };

type Props = {
  open: boolean;
  latitude: number;
  longitude: number;
  battery: number;
  dest: ChatPlace | null;
  voiceTick: number; // MapScreen bumps this when its mic button is tapped
  onVoice: (state: VoiceState) => void;
  onClose: () => void;
  onPick: (hit: ChatHit) => void;
  onNavigate: (hit: ChatHit) => void;
};

export default function ChatPanel({
  open,
  latitude,
  longitude,
  battery,
  dest,
  voiceTick,
  onVoice,
  onClose,
  onPick,
  onNavigate,
}: Props) {
  const { t, lang } = useI18n();
  const insets = useSafeAreaInsets();
  const { height: screenH } = useWindowDimensions();
  const scrollRef = useRef<ComponentRef<typeof ScrollView>>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [kb, setKb] = useState(0);
  const [messages, setMessages] = useState<Msg[]>(() => [
    { id: "welcome", role: "bot", text: welcomeText(lang), hits: [] },
  ]);

  useEffect(() => {
    setMessages((prev) => {
      if (prev.length === 1 && prev[0].id === "welcome") {
        return [{ id: "welcome", role: "bot", text: welcomeText(lang), hits: [] }];
      }
      return prev;
    });
  }, [lang]);

  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const show = Keyboard.addListener(showEvent, (e) => setKb(e.endCoordinates.height));
    const hide = Keyboard.addListener(hideEvent, () => setKb(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 60);
    return () => clearTimeout(timer);
  }, [messages, open, kb, busy]);

  const toHit = (s: api.ApiStation): ChatHit => ({
    id: s.id,
    name: s.name,
    lat: s.lat,
    lng: s.lng,
    city: s.city,
    source: s.source,
    km: typeof s.km === "number" ? s.km : haversineKm(latitude, longitude, s.lat, s.lng),
  });

  // Earlier turns, so Gemini can follow up ("what about the second one?").
  // Read from a ref so voice callbacks that outlive a render see the latest messages.
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const historyNow = (): api.ChatTurn[] =>
    messagesRef.current
      .filter((m) => m.id !== "welcome" && !m.offline)
      .map((m) => ({ role: m.role === "user" ? "user" : "model", text: m.text }));

  const send = async (raw: string) => {
    const text = raw.trim();
    if (!text || busy || voiceRef.current.phase !== "idle") return;
    const stamp = Date.now();
    const history = historyNow();
    setMessages((prev) => [...prev, { id: `${stamp}-u`, role: "user", text, hits: [] }]);
    setDraft("");

    let reply: Msg | null = null;
    if (api.backendConfigured) {
      setBusy(true);
      try {
        const res = await api.chat(
          { lat: latitude, lng: longitude, battery_pct: battery, lang },
          text,
          history,
          dest?.id
        );
        reply = { id: `${stamp}-b`, role: "bot", text: res.reply, hits: res.stations.map(toHit) };
      } catch {
        reply = null;
      } finally {
        setBusy(false);
      }
    }
    if (!reply) {
      const answer = replyTo(text, { lang, latitude, longitude, battery, dest });
      reply = {
        id: `${stamp}-b`,
        role: "bot",
        text: answer.text,
        hits: answer.hits,
        offline: api.backendConfigured,
      };
    }
    const done = reply;
    setMessages((prev) => [...prev, done]);
  };

  // ── Voice ──────────────────────────────────────────────────────────────────
  // Tap the mic → chime → record until a pause → server transcribes and answers →
  // the answer is spoken → it listens once more for a follow-up (silence ends it).
  // Async steps outlive renders, so they read the latest values through refs.
  const recorder = useAudioRecorder(RECORDING);
  const recState = useAudioRecorderState(recorder, 120);
  const speakerRef = useRef<Speaker | null>(null);
  if (!speakerRef.current) speakerRef.current = new Speaker();
  const detectorRef = useRef<SilenceDetector | null>(null);
  const turnRef = useRef(0); // bumping it cancels whatever voice step is in flight
  const voiceRef = useRef<VoiceState>({ phase: "idle", followUp: false, caption: "" });
  const [voice, setVoiceState] = useState<VoiceState>(voiceRef.current);
  const latest = useRef({ t, lang, latitude, longitude, battery, destId: dest?.id ?? null, onVoice });
  latest.current = { t, lang, latitude, longitude, battery, destId: dest?.id ?? null, onVoice };

  const setVoice = useCallback((next: VoiceState) => {
    voiceRef.current = next;
    setVoiceState(next);
    latest.current.onVoice(next);
  }, []);
  const goIdle = () => setVoice({ phase: "idle", followUp: false, caption: "" });

  const startListening = async (followUp: boolean) => {
    const { t: tt } = latest.current;
    if (!api.backendConfigured) {
      Alert.alert(tt.voiceTitle, tt.voiceNeedsServer);
      return;
    }
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) {
      Alert.alert(tt.voiceTitle, tt.voiceNoMic);
      goIdle();
      return;
    }
    speakerRef.current!.stop();
    const turn = ++turnRef.current;
    setVoice({ phase: "listening", followUp, caption: "" });
    await playListenCue();
    if (turn !== turnRef.current) return;
    try {
      await recordingMode();
      await recorder.prepareToRecordAsync();
      recorder.record();
      detectorRef.current = new SilenceDetector(followUp);
    } catch {
      if (turn === turnRef.current) goIdle();
    }
  };

  const speakError = async (turn: number, detail: string) => {
    const { t: tt, lang: lg } = latest.current;
    console.warn("[voice]", detail);
    setMessages((prev) => [
      ...prev,
      { id: `${Date.now()}-ve`, role: "bot", text: tt.voiceError, hits: [], note: detail },
    ]);
    setVoice({ phase: "speaking", followUp: false, caption: tt.voiceError });
    await speakerRef.current!.say(tt.voiceError, lg);
    if (turn === turnRef.current) goIdle();
  };

  const finishListening = async (action: "send" | "drop") => {
    if (voiceRef.current.phase !== "listening" || !detectorRef.current) return;
    const followUp = voiceRef.current.followUp;
    detectorRef.current = null;
    const turn = ++turnRef.current;
    setVoice({ phase: action === "send" ? "thinking" : "idle", followUp, caption: "" });
    let uri: string | null = null;
    let stopError = "";
    try {
      await recorder.stop();
      uri = recorder.uri;
    } catch (err) {
      stopError = err instanceof Error ? err.message : String(err);
    }
    await playbackMode().catch(() => {});
    if (action === "drop" || turn !== turnRef.current) return;
    if (!uri) return speakError(turn, `recording failed: ${stopError || "no file"}`);

    const w = latest.current;
    try {
      const res = await api.voice(
        { lat: w.latitude, lng: w.longitude, battery_pct: w.battery, lang: w.lang },
        uri,
        historyNow(),
        w.destId
      );
      if (turn !== turnRef.current) return;
      if (!res.heard) {
        // Silence or noise. After a follow-up prompt that just means "no more questions".
        if (followUp) return goIdle();
        setVoice({ phase: "speaking", followUp: false, caption: res.reply });
        await speakerRef.current!.say(res.reply, w.lang);
        if (turn === turnRef.current) goIdle();
        return;
      }
      const stamp = Date.now();
      setMessages((prev) => [
        ...prev,
        { id: `${stamp}-vu`, role: "user", text: res.transcript, hits: [], voice: true },
        { id: `${stamp}-vb`, role: "bot", text: res.reply, hits: res.stations.map(toHit) },
      ]);
      setVoice({ phase: "speaking", followUp: false, caption: res.reply });
      const finished = await speakerRef.current!.play(res.speech, w.lang);
      if (turn !== turnRef.current) return;
      if (finished) void voiceFns.current.startListening(true);
      else goIdle();
    } catch (err) {
      const detail =
        err instanceof api.ApiError
          ? `${err.status ? `HTTP ${err.status}: ` : ""}${err.message}`
          : err instanceof Error
            ? err.message
            : String(err);
      if (turn === turnRef.current) await speakError(turn, detail);
    }
  };

  /** Mic button: start, send now, or stop — depending on what voice is doing. */
  const toggleVoice = () => {
    const { phase } = voiceRef.current;
    if (phase === "idle") {
      void startListening(false);
    } else if (phase === "listening" && detectorRef.current) {
      void finishListening("send");
    } else {
      // Still chiming, waiting for the server, or speaking: cancel it.
      turnRef.current++;
      detectorRef.current = null;
      speakerRef.current!.stop();
      if (recorder.isRecording) void recorder.stop().catch(() => {});
      goIdle();
    }
  };

  const voiceFns = useRef({ startListening, finishListening, toggleVoice });
  voiceFns.current = { startListening, finishListening, toggleVoice };

  // Silence detection: runs on every meter update while recording.
  useEffect(() => {
    const detector = detectorRef.current;
    if (!detector || voiceRef.current.phase !== "listening" || !recState.isRecording) return;
    const verdict = detector.update(recState.metering);
    if (verdict !== "keep") void voiceFns.current.finishListening(verdict);
  }, [recState]);

  // The map's mic button.
  useEffect(() => {
    if (voiceTick > 0) voiceFns.current.toggleVoice();
  }, [voiceTick]);

  useEffect(
    () => () => {
      turnRef.current++;
      speakerRef.current?.stop();
    },
    []
  );

  const voiceLine =
    voice.phase === "listening"
      ? voice.followUp
        ? t.voiceFollowUp
        : t.voiceListening
      : voice.phase === "thinking"
        ? t.voiceThinking
        : voice.phase === "speaking"
          ? t.voiceSpeaking
          : "";

  // Expo apps are edge-to-edge, so the window never resizes for the keyboard:
  // the sheet has to lift itself. iOS reports the full keyboard height; Android
  // reports it minus the navigation bar, so add that inset back.
  const lift = kb ? (Platform.OS === "android" ? kb + insets.bottom : kb) : 0;
  const sheetH = Math.min(screenH * 0.78, screenH - lift - insets.top - 12);

  return (
    <View
      style={[
        styles.sheet,
        { bottom: lift, height: sheetH },
        !open && styles.hidden,
      ]}
      pointerEvents={open ? "auto" : "none"}
    >
      <View style={styles.handle}>
        <View style={styles.handleBar} />
        <View style={styles.titleRow}>
          <View>
            <Text style={styles.title}>{t.chatTitle}</Text>
            <Text style={styles.subtitle}>
              {api.backendConfigured ? t.chatAiTag : t.chatLocalTag}
            </Text>
          </View>
          <Pressable
            onPress={() => {
              Keyboard.dismiss();
              onClose();
            }}
            hitSlop={8}
          >
            <Text style={styles.close}>{t.chatClose}</Text>
          </Pressable>
        </View>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chipRow}
        contentContainerStyle={styles.chips}
        keyboardShouldPersistTaps="handled"
      >
        {suggestionChips(lang).map((chip) => (
          <Pressable key={chip} style={styles.chip} onPress={() => send(chip)}>
            <Text style={styles.chipTxt}>{chip}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <ScrollView
        ref={scrollRef}
        style={styles.thread}
        contentContainerStyle={styles.threadContent}
        keyboardShouldPersistTaps="handled"
      >
        {messages.map((msg) => (
          <View key={msg.id} style={msg.role === "user" ? styles.userWrap : styles.botWrap}>
            <View style={msg.role === "user" ? styles.userBubble : styles.botBubble}>
              <Text style={msg.role === "user" ? styles.userTxt : styles.botTxt}>
                {msg.voice ? "🎤 " : ""}
                {msg.text}
              </Text>
            </View>
            {msg.offline ? <Text style={styles.offlineNote}>{t.chatOffline}</Text> : null}
            {msg.note ? <Text style={styles.offlineNote}>{msg.note}</Text> : null}
            {msg.hits.map((hit) => {
              const where = cityLabel(hit.city, lang);
              return (
                <View key={hit.id} style={styles.card}>
                  <Text style={styles.cardName} numberOfLines={2}>
                    {hit.name || hit.id}
                  </Text>
                  <Text style={styles.cardMeta}>
                    {where ? `${where} · ` : ""}
                    {t.kmAway(hit.km < 10 ? hit.km.toFixed(1) : String(Math.round(hit.km)))}
                  </Text>
                  <View style={styles.cardActions}>
                    <Pressable style={styles.ghostBtn} onPress={() => onPick(hit)}>
                      <Text style={styles.ghostTxt}>{t.chatSetDest}</Text>
                    </Pressable>
                    <Pressable style={styles.navBtn} onPress={() => onNavigate(hit)}>
                      <Text style={styles.navTxt}>{t.startNav}</Text>
                    </Pressable>
                  </View>
                </View>
              );
            })}
          </View>
        ))}
        {busy ? (
          <View style={styles.botWrap}>
            <View style={styles.botBubble}>
              <Text style={styles.thinking}>{t.chatThinking}</Text>
            </View>
          </View>
        ) : null}
      </ScrollView>
      {voiceLine ? (
        <Pressable style={styles.voiceStrip} onPress={toggleVoice}>
          <View style={[styles.voiceDot, voice.phase === "listening" && styles.voiceDotLive]} />
          <Text style={styles.voiceStripTxt}>{voiceLine}</Text>
        </Pressable>
      ) : null}
      <View style={[styles.composer, { paddingBottom: kb ? 10 : insets.bottom + 10 }]}>
        <Pressable
          style={[styles.mic, voice.phase !== "idle" && styles.micLive]}
          onPress={toggleVoice}
          disabled={busy}
          hitSlop={6}
          accessibilityLabel={t.voiceTitle}
        >
          <Text style={styles.micTxt}>{voice.phase === "idle" ? "🎤" : "■"}</Text>
        </Pressable>
        <TextInput
          style={styles.input}
          placeholder={t.chatPlaceholder}
          placeholderTextColor="#9ca3af"
          value={draft}
          onChangeText={setDraft}
          returnKeyType="send"
          submitBehavior="submit"
          onSubmitEditing={() => send(draft)}
        />
        <Pressable
          style={[styles.send, (!draft.trim() || busy || voice.phase !== "idle") && styles.sendOff]}
          onPress={() => send(draft)}
          disabled={busy || voice.phase !== "idle"}
        >
          <Text style={styles.navTxt}>{t.chatSend}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "78%",
    backgroundColor: "#fff",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    elevation: 24,
    shadowOpacity: 0.2,
    shadowRadius: 12,
    zIndex: 30,
  },
  hidden: { display: "none" },
  handle: { paddingTop: 10, paddingHorizontal: 16 },
  handleBar: {
    alignSelf: "center",
    width: 42,
    height: 5,
    borderRadius: 3,
    backgroundColor: "#d1d5db",
    marginBottom: 8,
  },
  titleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontSize: 18, fontWeight: "800", color: "#111" },
  subtitle: { fontSize: 12, color: "#6b7280", marginTop: 1 },
  offlineNote: { fontSize: 11, color: "#9ca3af", marginLeft: 4 },
  thinking: { color: "#6b7280", fontStyle: "italic" },
  close: { color: "#16a34a", fontWeight: "700" },
  chipRow: { flexGrow: 0 },
  chips: { paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  chip: { backgroundColor: "#eff6ff", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 8 },
  chipTxt: { color: "#1d4ed8", fontWeight: "700", fontSize: 13 },
  thread: { flex: 1 },
  threadContent: { paddingHorizontal: 16, paddingBottom: 8, gap: 10 },
  userWrap: { alignItems: "flex-end" },
  botWrap: { alignItems: "flex-start", gap: 8 },
  userBubble: { maxWidth: "86%", backgroundColor: "#2563eb", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 10 },
  botBubble: { maxWidth: "92%", backgroundColor: "#f3f4f6", borderRadius: 16, paddingHorizontal: 12, paddingVertical: 10 },
  userTxt: { color: "#fff", lineHeight: 20 },
  botTxt: { color: "#111", lineHeight: 20 },
  card: { width: "100%", backgroundColor: "#f8fafc", borderRadius: 14, padding: 12, borderWidth: 1, borderColor: "#e5e7eb" },
  cardName: { fontWeight: "700", color: "#111" },
  cardMeta: { color: "#6b7280", marginTop: 2, marginBottom: 8 },
  cardActions: { flexDirection: "row", gap: 8 },
  ghostBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#2563eb",
    borderRadius: 12,
    paddingVertical: 8,
    alignItems: "center",
  },
  ghostTxt: { color: "#2563eb", fontWeight: "700", fontSize: 13 },
  navBtn: { flex: 1, backgroundColor: "#2563eb", borderRadius: 12, paddingVertical: 8, alignItems: "center" },
  navTxt: { color: "#fff", fontWeight: "700", fontSize: 13 },
  composer: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#e5e7eb",
  },
  input: {
    flex: 1,
    backgroundColor: "#f3f4f6",
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#111",
  },
  send: { backgroundColor: "#16a34a", borderRadius: 14, paddingHorizontal: 16, justifyContent: "center" },
  sendOff: { opacity: 0.45 },
  mic: {
    width: 44,
    borderRadius: 14,
    backgroundColor: "#eff6ff",
    alignItems: "center",
    justifyContent: "center",
  },
  micLive: { backgroundColor: "#dc2626" },
  micTxt: { fontSize: 18, color: "#fff" },
  voiceStrip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    backgroundColor: "#fef2f2",
  },
  voiceDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: "#9ca3af" },
  voiceDotLive: { backgroundColor: "#dc2626" },
  voiceStripTxt: { flex: 1, color: "#991b1b", fontWeight: "600", fontSize: 13 },
});
