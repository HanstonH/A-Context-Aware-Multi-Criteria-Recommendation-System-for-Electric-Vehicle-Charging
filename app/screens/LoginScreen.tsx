import { useMemo, useState } from "react";
import {
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useI18n } from "../i18n";
import { colors, useTheme } from "../theme";

type Props = {
  onLogin: () => void;
};

export default function LoginScreen({ onLogin }: Props) {
  const { t } = useI18n();
  const { dark } = useTheme();
  const styles = useMemo(() => makeStyles(dark), [dark]);
  const [email, setEmail] = useState("demo@ev.local");
  const [password, setPassword] = useState("demo123");

  const enter = () => {
    Keyboard.dismiss();
    onLogin();
  };

  return (
    <KeyboardAvoidingView
      style={styles.wrap}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={styles.inner}
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
          placeholderTextColor={colors(dark).muted}
        />

        <Text style={styles.label}>{t.password}</Text>
        <TextInput
          style={styles.input}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          placeholder={t.password}
          placeholderTextColor={colors(dark).muted}
        />
        <Text style={styles.forgot}>{t.forgot}</Text>

        <Pressable style={styles.primary} onPress={enter}>
          <Text style={styles.primaryText}>{t.login}</Text>
        </Pressable>

        <Text style={styles.or}>{t.orLogin}</Text>
        <View style={styles.row}>
          <Pressable style={styles.outline} onPress={enter}>
            <Text style={styles.outlineTxt}>Google</Text>
          </Pressable>
          <Pressable style={styles.outline} onPress={enter}>
            <Text style={styles.outlineTxt}>Apple</Text>
          </Pressable>
        </View>
        <Pressable onPress={enter}>
          <Text style={styles.footer}>{t.noAccount}</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function makeStyles(dark: boolean) {
  const p = colors(dark);
  return StyleSheet.create({
  wrap: { flex: 1, backgroundColor: p.bg },
  inner: { flexGrow: 1, padding: 28, justifyContent: "center" },
  brand: { fontSize: 32, fontWeight: "700", color: p.text, textAlign: "center" },
  tagline: { color: p.muted, textAlign: "center", marginBottom: 32, marginTop: 8 },
  label: { color: p.textBody, marginBottom: 6, marginTop: 10 },
  input: {
    borderWidth: 1,
    borderColor: p.border,
    backgroundColor: p.sheet,
    color: p.text,
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
  or: { textAlign: "center", color: p.muted, marginVertical: 16 },
  row: { flexDirection: "row", gap: 12 },
  outline: {
    flex: 1,
    borderWidth: 1,
    borderColor: p.border,
    borderRadius: 24,
    paddingVertical: 12,
    alignItems: "center",
  },
  outlineTxt: { color: p.text, fontWeight: "600" },
  footer: { textAlign: "center", marginTop: 24, color: p.muted },
  });
}
