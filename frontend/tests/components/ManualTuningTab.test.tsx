import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { ManualTuningTab } from "../../src/components/manual/ManualTuningTab";
import {
  schemaFixture,
  simulateResultFixture,
  systemFixture,
} from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

describe("ManualTuningTab", () => {
  it("renders schema-driven sliders and submits a simulation", async () => {
    const user = userEvent.setup();
    const onResult = vi.fn();
    let submittedParams: Record<string, number> | undefined;

    server.use(
      http.get("*/api/v1/systems/*/schema", () => HttpResponse.json(schemaFixture)),
      http.post("*/api/v1/systems/*/simulate", async ({ request }) => {
        const body = (await request.json()) as { params: Record<string, number> };
        submittedParams = body.params;
        return HttpResponse.json(simulateResultFixture);
      }),
    );

    renderWithProviders(
      <ManualTuningTab system={systemFixture} result={null} onResult={onResult} />,
    );

    const kpSlider = await screen.findByLabelText("Kp slider");
    expect(kpSlider).toHaveAttribute("min", "0.1");
    expect(kpSlider).toHaveAttribute("max", "60");
    expect(screen.getByLabelText("Ki slider")).toBeInTheDocument();
    expect(screen.getByLabelText("Kd slider")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Run simulation" }));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(simulateResultFixture));
    expect(submittedParams?.Kp).toBeGreaterThan(0);
  });

  it("shows a backend error and re-enables the form", async () => {
    const user = userEvent.setup();

    server.use(
      http.get("*/api/v1/systems/*/schema", () => HttpResponse.json(schemaFixture)),
      http.post("*/api/v1/systems/*/simulate", () =>
        HttpResponse.json(
          { error: { code: "engine_error", message: "Engine exploded" } },
          { status: 500 },
        ),
      ),
    );

    renderWithProviders(
      <ManualTuningTab system={systemFixture} result={null} onResult={vi.fn()} />,
    );

    await screen.findByLabelText("Kp slider");
    await user.click(screen.getByRole("button", { name: "Run simulation" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Engine exploded");
    expect(screen.getByRole("button", { name: "Run simulation" })).toBeEnabled();
  });
});
