import { useState } from "react";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { LanguageProvider } from "./i18n";
import LoginScreen from "./screens/LoginScreen";
import MapScreen from "./screens/MapScreen";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false);

  return (
    <SafeAreaProvider>
      <LanguageProvider>
        {loggedIn ? (
          <MapScreen onLogout={() => setLoggedIn(false)} />
        ) : (
          <LoginScreen onLogin={() => setLoggedIn(true)} />
        )}
        <StatusBar style="auto" />
      </LanguageProvider>
    </SafeAreaProvider>
  );
}
