import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { JobProgressPanel } from "../../src/components/auto/JobProgressPanel";
import { runningJobFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

describe("JobProgressPanel", () => {
  it("renders live progress and the polling fallback", async () => {
    server.use(
      http.get("*/api/v1/jobs/*", () => HttpResponse.json(runningJobFixture)),
    );

    renderWithProviders(
      <JobProgressPanel jobId={runningJobFixture.job_id} onSucceeded={vi.fn()} onReset={vi.fn()} />,
    );

    expect(await screen.findByText("Background optimization")).toBeInTheDocument();
    expect(await screen.findByText("75.000")).toBeInTheDocument();
    expect(screen.getByText("14.200")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel job" })).toBeInTheDocument();
    expect(
      await screen.findByText(/falling back to polling/i),
    ).toBeInTheDocument();
  });

  it("cancels a running job", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();
    const cancelled = { ...runningJobFixture, status: "cancelled" as const };
    server.use(
      http.get("*/api/v1/jobs/*", () => HttpResponse.json(runningJobFixture)),
      http.post("*/api/v1/jobs/*/cancel", () => HttpResponse.json(cancelled)),
    );

    renderWithProviders(
      <JobProgressPanel jobId={runningJobFixture.job_id} onSucceeded={vi.fn()} onReset={vi.fn()} />,
    );

    await user.click(await screen.findByRole("button", { name: "Cancel job" }));

    expect(await screen.findByText("The optimization was cancelled. Partial progress is not saved as a result.")).toBeInTheDocument();
  });
});
