import { describe, expect, it } from "vitest";
import { applyTheme, getStoredTheme, toggleTheme } from "./theme";

describe("theme", () => {
  it("persists dark and returns to light", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(getStoredTheme()).toBe("dark");
    const next = toggleTheme("dark");
    expect(next).toBe("light");
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(getStoredTheme()).toBe("light");
  });
});
