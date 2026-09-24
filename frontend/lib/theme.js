import { createContext, useContext, useEffect, useMemo, useState } from "react";

const ThemeContext = createContext({ theme: "dark", toggleTheme: () => { } });

function getInitialTheme() {
  if (typeof window === "undefined") return "dark";
  const saved = window.localStorage.getItem("citypulse-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function ThemeProvider({ children }) {
  // Always start with "dark" so the server HTML and the first browser render match
  // (reading localStorage here caused a hydration error: sun vs moon icon).
  const [theme, setTheme] = useState("dark");
  const [ready, setReady] = useState(false);

  // After hydration, switch to the saved / system theme.
  useEffect(() => {
    setTheme(getInitialTheme());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return; // don't overwrite the saved theme with the default before we've read it
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    window.localStorage.setItem("citypulse-theme", theme);
    window.dispatchEvent(new CustomEvent("citypulse-theme-change", { detail: theme }));

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "light" ? "#f4f8fc" : "#06101d");
  }, [theme, ready]);

  useEffect(() => {
    const onSystem = (event) => {
      if (window.localStorage.getItem("citypulse-theme")) return;
      setTheme(event.matches ? "light" : "dark");
    };
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    media?.addEventListener?.("change", onSystem);
    return () => media?.removeEventListener?.("change", onSystem);
  }, []);

  const value = useMemo(() => ({
    theme,
    isLight: theme === "light",
    setTheme,
    toggleTheme: () => setTheme((current) => (current === "dark" ? "light" : "dark")),
  }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}