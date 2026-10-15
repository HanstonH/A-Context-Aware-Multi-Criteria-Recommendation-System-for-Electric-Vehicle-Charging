import { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useI18n } from "../i18n";

type Props = {
  onLogin: () => void;
};

export default function LoginScreen({ onLogin }: Props) {
  const { t } = useI18n();
  const [email, setEmail] = useState("demo@ev.local");
  const [password, setPassword] = useState("demo123");

  return (
    <KeyboardAvoidingView
      style={styles.wrap}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Text style={styles.brand}>MapExplore</Text>
      <Text style={styles.tagline}>{t.tagline}</Text>

      <Text style={styles.label}>{t.email}</Text>
      <TextInput
        style={styles.input}
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
        placeholder="you@example.com"
      />

      <Text style={styles.label}>{t.password}</Text>
      <TextInput
        style={styles.input}
        secureTextEntry
        value={password}
        onChangeText={setPassword}
        placeholder={t.password}
      />
      <Text style={styles.forgot}>{t.forgot}</Text>

      <Pressable style={styles.primary} onPress={onLogin}>
        <Text style={styles.primaryText}>{t.login}</Text>
      </Pressable>

      <Text style={styles.or}>{t.orLogin}</Text>
      <View style={styles.row}>
        <Pressable style={styles.outline}>
          <Text>Google</Text>
        </Pressable>
        <Pressable style={styles.outline}>
          <Text>Apple</Text>
        </Pressable>
      </View>
      <Text style={styles.footer}>{t.noAccount}</Text>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#fff", padding: 28, justifyContent: "center" },
  brand: { fontSize: 32, fontWeight: "700", color: "#111", textAlign: "center" },
  tagline: { color: "#6b7280", textAlign: "center", marginBottom: 32, marginTop: 8 },
  label: { color: "#374151", marginBottom: 6, marginTop: 10 },
  input: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
  },
  forgot: { color: "#16a34a", textAlign: "right", marginTop: 8, marginBottom: 16 },
  primary: {
    backgroundColor: "#16a34a",
    borderRadius: 24,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  or: { textAlign: "center", color: "#9ca3af", marginVertical: 16 },
  row: { flexDirection: "row", gap: 12 },
  outline: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 24,
    paddingVertical: 12,
    alignItems: "center",
  },
  footer: { textAlign: "center", marginTop: 24, color: "#6b7280" },
});
