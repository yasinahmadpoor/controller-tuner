import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { useOptimize } from "../../src/hooks/queries";
import { optimizeResultFixture, systemFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { createTestQueryClient } from "../../src/test/utils";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
  );
}

const request = {
  ga_config: { population_size: 5, generations: 2, seed: 42, max_wall_clock: 30 },
};

describe("useOptimize", () => {
  it("returns optimization results on success", async () => {
    server.use(
      http.post("*/api/v1/systems/*/optimize", () =>
        HttpResponse.json(optimizeResultFixture),
      ),
    );
    const { result } = renderHook(() => useOptimize(systemFixture.system_id), { wrapper });

    let data;
    await act(async () => {
      data = await result.current.mutateAsync(request);
    });

    expect(data).toEqual(optimizeResultFixture);
  });

  it("surfaces 422 validation errors", async () => {
    server.use(
      http.post("*/api/v1/systems/*/optimize", () =>
        HttpResponse.json(
          { error: { code: "validation_error", message: "Invalid range" } },
          { status: 422 },
        ),
      ),
    );
    const { result } = renderHook(() => useOptimize(systemFixture.system_id), { wrapper });

    await act(async () => {
      await expect(result.current.mutateAsync(request)).rejects.toMatchObject({
        status: 422,
        code: "validation_error",
      });
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it("surfaces 500 engine errors", async () => {
    server.use(
      http.post("*/api/v1/systems/*/optimize", () =>
        HttpResponse.json(
          { error: { code: "engine_error", message: "GA failed" } },
          { status: 500 },
        ),
      ),
    );
    const { result } = renderHook(() => useOptimize(systemFixture.system_id), { wrapper });

    await act(async () => {
      await expect(result.current.mutateAsync(request)).rejects.toMatchObject({
        status: 500,
        code: "engine_error",
      });
    });
  });
});
