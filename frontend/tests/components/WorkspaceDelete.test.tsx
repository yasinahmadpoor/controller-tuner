import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { WorkspacePage } from "../../src/components/workspace/WorkspacePage";
import { schemaFixture, systemFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

describe("Workspace delete", () => {
  it("deletes the current workspace and returns to the catalog", async () => {
    const user = userEvent.setup();
    let deleted = false;
    server.use(
      http.get(`*/api/v1/systems/${systemFixture.system_id}`, () =>
        HttpResponse.json(systemFixture),
      ),
      http.get("*/api/v1/systems/*/schema", () => HttpResponse.json(schemaFixture)),
      http.delete("*/api/v1/systems/*", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(
      <Routes>
        <Route path="/systems/:systemId/:tab" element={<WorkspacePage />} />
        <Route path="/systems" element={<div>Catalog page</div>} />
      </Routes>,
      { route: `/systems/${systemFixture.system_id}/manual` },
    );

    await user.click(await screen.findByRole("button", { name: "Delete workspace" }));
    await user.click(screen.getByRole("button", { name: "Delete workspace permanently" }));

    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByText("Catalog page")).toBeInTheDocument();
  });
});
