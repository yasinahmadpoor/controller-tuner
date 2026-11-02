import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { AutoTuneForm } from "../../src/components/auto/AutoTuneForm";
import { AutoTuneTab } from "../../src/components/auto/AutoTuneTab";
import {
  optimizeJobFixture,
  optimizeResultFixture,
  systemFixture,
} from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

describe("AutoTuneForm", () => {
  it("pre-fills case-study defaults", () => {
    renderWithProviders(<AutoTuneForm system={systemFixture} onOptimized={vi.fn()} />);

    expect(screen.getByLabelText("Kp low")).toHaveValue(1);
    expect(screen.getByLabelText("Kp high")).toHaveValue(50);
    expect(screen.getByLabelText("mse weight")).toHaveValue(1);
    expect(screen.getByLabelText("mse target")).toHaveValue(0.05);
    expect(screen.getByLabelText("Population")).toHaveValue(20);
    expect(screen.getByLabelText("Generations")).toHaveValue(30);
    expect(screen.getByLabelText("Seed")).toHaveValue(42);
    expect(screen.getByLabelText("Max wall clock")).toHaveValue(120);
    expect(screen.getByLabelText("Run in background (async)")).toBeChecked();
  });

  it("restores defaults after edits", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AutoTuneForm system={systemFixture} onOptimized={vi.fn()} />);
    const kpLow = screen.getByLabelText("Kp low");

    await user.clear(kpLow);
    await user.type(kpLow, "5");
    expect(kpLow).toHaveValue(5);

    await user.click(screen.getByRole("button", { name: "Reset to defaults" }));
    expect(screen.getByLabelText("Kp low")).toHaveValue(1);
  });

  it("blocks inverted ranges before submitting", async () => {
    const user = userEvent.setup();
    const onOptimized = vi.fn();
    renderWithProviders(<AutoTuneForm system={systemFixture} onOptimized={onOptimized} />);
    const kpLow = screen.getByLabelText("Kp low");

    await user.clear(kpLow);
    await user.type(kpLow, "60");
    await user.click(screen.getByRole("button", { name: "Run optimization" }));

    expect(await screen.findByText("Low must be less than high")).toBeInTheDocument();
    expect(onOptimized).not.toHaveBeenCalled();
  });

  it("blocks negative weights before submitting", async () => {
    const user = userEvent.setup();
    const onOptimized = vi.fn();
    renderWithProviders(<AutoTuneForm system={systemFixture} onOptimized={onOptimized} />);
    const mseWeight = screen.getByLabelText("mse weight");

    await user.clear(mseWeight);
    await user.type(mseWeight, "-1");
    await user.click(screen.getByRole("button", { name: "Run optimization" }));

    expect(await screen.findByText("Must be at least 0")).toBeInTheDocument();
    expect(onOptimized).not.toHaveBeenCalled();
  });

  it("disables auto-tune for systems without the optimize capability", () => {
    renderWithProviders(
      <AutoTuneTab system={{ ...systemFixture, capabilities: ["simulate"] }} />,
    );

    expect(screen.getByText("Auto-tune unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run optimization" })).not.toBeInTheDocument();
  });

  it("submits the optimization and returns the result", async () => {
    const user = userEvent.setup();
    const onOptimized = vi.fn();
    server.use(
      http.post("*/api/v1/systems/*/optimize", () =>
        HttpResponse.json(optimizeResultFixture),
      ),
    );
    renderWithProviders(<AutoTuneForm system={systemFixture} onOptimized={onOptimized} />);

    await user.click(screen.getByLabelText("Run in background (async)"));
    await user.click(screen.getByRole("button", { name: "Run optimization" }));

    await waitFor(() => expect(onOptimized).toHaveBeenCalled());
    expect(onOptimized.mock.calls[0][0]).toEqual(optimizeResultFixture);
    expect(onOptimized.mock.calls[0][1]).toMatchObject({ mse: 0.05 });
  });

  it("queues a background optimization by default", async () => {
    const user = userEvent.setup();
    const onJobCreated = vi.fn();
    server.use(
      http.post("*/api/v1/systems/*/optimize", () =>
        HttpResponse.json(optimizeJobFixture, { status: 202 }),
      ),
    );
    renderWithProviders(
      <AutoTuneForm
        system={systemFixture}
        onOptimized={vi.fn()}
        onJobCreated={onJobCreated}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Run optimization" }));

    await waitFor(() => expect(onJobCreated).toHaveBeenCalled());
    expect(onJobCreated.mock.calls[0][0]).toEqual(optimizeJobFixture);
    expect(onJobCreated.mock.calls[0][1]).toMatchObject({ mse: 0.05 });
  });
});
