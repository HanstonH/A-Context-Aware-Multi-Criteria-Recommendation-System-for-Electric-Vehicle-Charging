import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

let remembered = false;

type ThemeValue = {
  dark: boolean;
  setDark: (next: boolean) => void;
};

const ThemeContext = createContext<ThemeValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDarkState] = useState(remembered);
  const value = useMemo<ThemeValue>(() => {
    const setDark = (next: boolean) => {
      remembered = next;
      setDarkState(next);
    };
    return { dark, setDark };
  }, [dark]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be inside ThemeProvider");
  return ctx;
}

export function colors(dark: boolean) {
  return {
    bg: dark ? "#0b1220" : "#ffffff",
    sheet: dark ? "#111827" : "#ffffff",
    card: dark ? "#1f2937" : "#f3f4f6",
    cardOn: dark ? "#14532d" : "#dcfce7",
    text: dark ? "#f9fafb" : "#111827",
    textBody: dark ? "#d1d5db" : "#374151",
    muted: dark ? "#9ca3af" : "#6b7280",
    line: dark ? "#374151" : "#e5e7eb",
    handle: dark ? "#4b5563" : "#d1d5db",
    float: dark ? "rgba(17,24,39,0.94)" : "rgba(255,255,255,0.92)",
    soft: dark ? "#052e16" : "#f0fdf4",
    greenText: dark ? "#86efac" : "#166534",
    ink: dark ? "#f9fafb" : "#111111",
    border: dark ? "#374151" : "#e5e7eb",
  };
}
