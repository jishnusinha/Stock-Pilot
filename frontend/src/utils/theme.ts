export type ThemeName = "light" | "dark";

const KEY = "stockpilot-theme";

export function getStoredTheme(): ThemeName {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

export function applyTheme(theme: ThemeName): void {
  if (theme === "dark") document.documentElement.dataset.theme = "dark";
  else delete document.documentElement.dataset.theme;
  localStorage.setItem(KEY, theme);
}

export function toggleTheme(current: ThemeName): ThemeName {
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
