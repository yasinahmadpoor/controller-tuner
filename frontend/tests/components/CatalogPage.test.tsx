import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { CatalogPage } from "../../src/components/catalog/CatalogPage";
import { catalogEntry, systemFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

const otherWorkspace = {
  ...systemFixture,
  system_id: "99999999-9999-9999-9999-999999999999",
  created_at: "2026-01-03T00:00:00Z",
};

function systemsResponse(items = [systemFixture]) {
  return HttpResponse.json({ items, total: items.length, limit: 100, offset: 0 });
}

describe("CatalogPage", () => {
  it("creates a workspace when the catalog entry has none", async () => {
    server.use(
      http.get("*/api/v1/catalog", () => HttpResponse.json({ items: [catalogEntry] })),
      http.get("*/api/v1/systems", () => systemsResponse([])),
    );

    renderWithProviders(<CatalogPage />);

    expect(await screen.findByText("Ball Beam")).toBeInTheDocument();
    expect(screen.getByText("Balance a ball on a beam")).toBeInTheDocument();
    expect(screen.getByText("simulate")).toBeInTheDocument();
    expect(screen.getByText("optimize")).toBeInTheDocument();
    expect(screen.getByText("No workspace yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create workspace" })).toBeInTheDocument();
  });

  it("opens the existing workspace when there is only one", async () => {
    server.use(
      http.get("*/api/v1/catalog", () => HttpResponse.json({ items: [catalogEntry] })),
      http.get("*/api/v1/systems", () => systemsResponse([systemFixture])),
    );

    renderWithProviders(<CatalogPage />);

    expect(await screen.findByRole("button", { name: "Open workspace" })).toBeInTheDocument();
    expect(screen.getByText("1 existing workspace with saved history.")).toBeInTheDocument();
  });

  it("shows a picker when multiple workspaces exist", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("*/api/v1/catalog", () => HttpResponse.json({ items: [catalogEntry] })),
      http.get("*/api/v1/systems", () =>
        systemsResponse([otherWorkspace, systemFixture]),
      ),
    );

    renderWithProviders(<CatalogPage />);

    await user.click(await screen.findByRole("button", { name: "Choose workspace (2)" }));

    const dialog = screen.getByRole("dialog", { name: "Choose a Ball Beam workspace" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Open workspace" })).toHaveLength(2);
    expect(screen.getByText(systemFixture.system_id)).toBeInTheDocument();
    expect(screen.getByText(otherWorkspace.system_id)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create new workspace" })).toBeInTheDocument();
  });

  it("lists recent workspaces for direct resume", async () => {
    server.use(
      http.get("*/api/v1/catalog", () => HttpResponse.json({ items: [catalogEntry] })),
      http.get("*/api/v1/systems", () =>
        systemsResponse([otherWorkspace, systemFixture]),
      ),
    );

    renderWithProviders(<CatalogPage />);

    expect(await screen.findByText("Recent workspaces")).toBeInTheDocument();
    expect(screen.getByText("2 total")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Open" })).toHaveLength(2);
  });

  it("shows a readable error when the catalog fails", async () => {
    server.use(
      http.get("*/api/v1/catalog", () =>
        HttpResponse.json(
          { error: { code: "engine_error", message: "Catalog is temporarily unavailable" } },
          { status: 500 },
        ),
      ),
      http.get("*/api/v1/systems", () => systemsResponse([])),
    );

    renderWithProviders(<CatalogPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Catalog is temporarily unavailable",
    );
  });
});
