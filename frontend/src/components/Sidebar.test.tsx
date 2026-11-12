import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";

vi.mock("../api/client", () => ({
  api: {
    health: () => Promise.resolve({ models_available: 10, models_expected: 10, db_ready: true, status: "ok" }),
  },
}));

describe("sidebar", () => {
  it("lists the product routes", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: /Command Center/i }).getAttribute("href")).toBe("/");
    expect(screen.getByRole("link", { name: /Inventory/i }).getAttribute("href")).toBe("/inventory");
    expect(screen.getByRole("link", { name: /What-If Simulator/i }).getAttribute("href")).toBe("/simulator");
    expect(screen.getByRole("link", { name: /Agent Intelligence/i }).getAttribute("href")).toBe("/agents");
    expect(screen.getByRole("link", { name: /Model Performance/i }).getAttribute("href")).toBe("/performance");
    expect(screen.getByRole("link", { name: /Reorders/i }).getAttribute("href")).toBe("/reorders");
  });
});
