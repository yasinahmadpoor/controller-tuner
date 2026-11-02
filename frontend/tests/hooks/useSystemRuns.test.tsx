import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useDeleteRun, useSystemRuns } from "../../src/hooks/queries";
import { simulationRun, systemFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { createTestQueryClient } from "../../src/test/utils";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
  );
}

describe("useSystemRuns", () => {
  it("fetches paginated history", async () => {
    server.use(
      http.get("*/api/v1/systems/*/simulations", ({ request }) => {
        const url = new URL(request.url);
        const offset = Number(url.searchParams.get("offset") ?? "0");
        return HttpResponse.json({
          items: [{ ...simulationRun, run_id: `run-${offset}` }],
          total: 25,
          limit: 10,
          offset,
        });
      }),
    );

    const { result, rerender } = renderHook(
      ({ offset }: { offset: number }) =>
        useSystemRuns(systemFixture.system_id, "simulation", 10, offset),
      { wrapper, initialProps: { offset: 0 } },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0].run_id).toBe("run-0");

    rerender({ offset: 10 });

    await waitFor(() =>
      expect(result.current.data?.items[0].run_id).toBe("run-10"),
    );
    expect(result.current.data?.total).toBe(25);
  });

  it("deletes a run through the API", async () => {
    let deleted = false;
    server.use(
      http.delete("*/api/v1/simulations/*", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const { result } = renderHook(
      () => useDeleteRun(systemFixture.system_id),
      { wrapper },
    );

    await act(async () => {
      await result.current.mutateAsync({
        runId: simulationRun.run_id,
        type: "simulation",
      });
    });

    expect(deleted).toBe(true);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
