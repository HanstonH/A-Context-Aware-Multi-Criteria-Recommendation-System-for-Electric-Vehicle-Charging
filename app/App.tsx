import { useState } from "react";
import { StatusBar } from "expo-status-bar";
import { LanguageProvider } from "./i18n";
import LoginScreen from "./screens/LoginScreen";
import MapScreen from "./screens/MapScreen";
import { ThemeProvider, useTheme } from "./theme";

function ThemedStatusBar() {
  const { dark } = useTheme();
  return <StatusBar style={dark ? "light" : "dark"} />;
}

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false);

  return (
    <LanguageProvider>
      <ThemeProvider>
        {loggedIn ? (
          <MapScreen onLogout={() => setLoggedIn(false)} />
        ) : (
          <LoginScreen onLogin={() => setLoggedIn(true)} />
        )}
        <ThemedStatusBar />
      </ThemeProvider>
    </LanguageProvider>
  );
}
