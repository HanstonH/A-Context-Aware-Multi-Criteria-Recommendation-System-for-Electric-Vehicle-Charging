import { useEffect, useRef, useState, type ComponentRef } from "react";
import {
  Keyboard,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  cityLabel,
  replyTo,
  suggestionChips,
  welcomeText,
  type ChatHit,
  type ChatPlace,
} from "../chatbot";
import { useI18n } from "../i18n";

type Msg = { id: string; role: "user" | "bot"; text: string; hits: ChatHit[] };

type Props = {
  open: boolean;
  latitude: number;
  longitude: number;
  battery: number;
  dest: ChatPlace | null;
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
  onClose,
  onPick,
  onNavigate,
}: Props) {
  const { t, lang } = useI18n();
  const scrollRef = useRef<ComponentRef<typeof ScrollView>>(null);
  const [draft, setDraft] = useState("");
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
  }, [messages, open, kb]);

  const send = (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    const answer = replyTo(text, { lang, latitude, longitude, battery, dest });
    const stamp = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: `${stamp}-u`, role: "user", text, hits: [] },
      { id: `${stamp}-b`, role: "bot", text: answer.text, hits: answer.hits },
    ]);
    setDraft("");
  };

  return (
    <View
      style={[
        styles.sheet,
        { bottom: Platform.OS === "ios" ? kb : 0, height: kb && Platform.OS === "ios" ? "56%" : "78%" },
        !open && styles.hidden,
      ]}
      pointerEvents={open ? "auto" : "none"}
    >
      <View style={styles.handle}>
        <View style={styles.handleBar} />
        <View style={styles.titleRow}>
          <Text style={styles.title}>{t.chatTitle}</Text>
          <Pressable onPress={onClose} hitSlop={8}>
            <Text style={styles.close}>{t.chatClose}</Text>
          </Pressable>
        </View>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
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
              <Text style={msg.role === "user" ? styles.userTxt : styles.botTxt}>{msg.text}</Text>
            </View>
            {msg.hits.map((hit) => {
              const where = cityLabel(hit.city, lang);
              return (
                <View key={hit.id} style={styles.card}>
                  <Text style={styles.cardName} numberOfLines={2}>
                    {hit.name || hit.id}
                  </Text>
                  <Text style={styles.cardMeta}>
                    {where ? `${where} · ` : ""}
                    {hit.km < 10 ? hit.km.toFixed(1) : Math.round(hit.km)} {t.kmLabel}
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
      </ScrollView>
      <View style={styles.composer}>
        <TextInput
          style={styles.input}
          placeholder={t.chatPlaceholder}
          placeholderTextColor="#9ca3af"
          value={draft}
          onChangeText={setDraft}
          returnKeyType="send"
          onSubmitEditing={() => send(draft)}
        />
        <Pressable style={[styles.send, !draft.trim() && styles.sendOff]} onPress={() => send(draft)}>
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
    paddingBottom: 16,
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
  close: { color: "#16a34a", fontWeight: "700" },
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
  composer: { flexDirection: "row", gap: 8, paddingHorizontal: 16, paddingTop: 8 },
  input: {
    flex: 1,
    backgroundColor: "#f3f4f6",
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#111",
  },
  send: { backgroundColor: "#16a34a", borderRadius: 14, paddingHorizontal: 14, justifyContent: "center" },
  sendOff: { opacity: 0.45 },
});
