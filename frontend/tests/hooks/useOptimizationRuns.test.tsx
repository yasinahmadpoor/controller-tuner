import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useOptimizationRuns, useRun } from "../../src/hooks/queries";
import {
  optimizationDetailFixture,
  optimizationRun,
  systemFixture,
} from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { createTestQueryClient } from "../../src/test/utils";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
  );
}

describe("useOptimizationRuns", () => {
  it("paginates optimization history", async () => {
    server.use(
      http.get("*/api/v1/systems/*/optimizations", ({ request }) => {
        const url = new URL(request.url);
        const offset = Number(url.searchParams.get("offset") ?? "0");
        return HttpResponse.json({
          items: [{ ...optimizationRun, run_id: `opt-${offset}` }],
          total: 25,
          limit: 10,
          offset,
        });
      }),
    );

    const { result, rerender } = renderHook(
      ({ offset }: { offset: number }) =>
        useOptimizationRuns(systemFixture.system_id, 10, offset),
      { wrapper, initialProps: { offset: 0 } },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0].run_id).toBe("opt-0");

    rerender({ offset: 10 });
    await waitFor(() =>
      expect(result.current.data?.items[0].run_id).toBe("opt-10"),
    );
  });

  it("reopens a persisted optimization run", async () => {
    server.use(
      http.get("*/api/v1/optimizations/*", () =>
        HttpResponse.json(optimizationDetailFixture),
      ),
    );

    const { result } = renderHook(
      () => useRun(optimizationDetailFixture.run_id, "optimization"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      run_id: optimizationDetailFixture.run_id,
      best_params: optimizationDetailFixture.best_params,
      stop_reason: "normal",
    });
  });
});
