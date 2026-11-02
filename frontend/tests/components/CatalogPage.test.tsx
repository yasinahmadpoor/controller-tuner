import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { CatalogPage } from "../../src/components/catalog/CatalogPage";
import { catalogEntry } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

describe("CatalogPage", () => {
  it("renders case-study cards with capabilities", async () => {
    server.use(
      http.get("*/api/v1/catalog", () =>
        HttpResponse.json({ items: [catalogEntry] }),
      ),
    );

    renderWithProviders(<CatalogPage />);

    expect(await screen.findByText("Ball Beam")).toBeInTheDocument();
    expect(screen.getByText("Balance a ball on a beam")).toBeInTheDocument();
    expect(screen.getByText("simulate")).toBeInTheDocument();
    expect(screen.getByText("optimize")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open workspace" })).toBeInTheDocument();
  });

  it("shows a readable error when the catalog fails", async () => {
    server.use(
      http.get("*/api/v1/catalog", () =>
        HttpResponse.json(
          { error: { code: "engine_error", message: "Catalog is temporarily unavailable" } },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(<CatalogPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Catalog is temporarily unavailable",
    );
  });
});
