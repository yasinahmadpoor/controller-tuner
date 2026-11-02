import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { ApiError } from "../../src/api/client";
import { useSimulate } from "../../src/hooks/queries";
import { simulateResultFixture, systemFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { createTestQueryClient } from "../../src/test/utils";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
  );
}

describe("useSimulate", () => {
  it("returns the simulation result on success", async () => {
    server.use(
      http.post("*/api/v1/systems/*/simulate", () =>
        HttpResponse.json(simulateResultFixture),
      ),
    );
    const { result } = renderHook(() => useSimulate(systemFixture.system_id), { wrapper });

    let data;
    await act(async () => {
      data = await result.current.mutateAsync({
        controller_type: "PID",
        params: { Kp: 10, Ki: 1, Kd: 2 },
      });
    });

    expect(data).toEqual(simulateResultFixture);
  });

  it("surfaces backend error codes", async () => {
    server.use(
      http.post("*/api/v1/systems/*/simulate", () =>
        HttpResponse.json(
          { error: { code: "invalid_parameters", message: "Bad gains" } },
          { status: 422 },
        ),
      ),
    );
    const { result } = renderHook(() => useSimulate(systemFixture.system_id), { wrapper });

    await act(async () => {
      await expect(
        result.current.mutateAsync({ controller_type: "PID", params: { Kp: 1 } }),
      ).rejects.toMatchObject({ status: 422, code: "invalid_parameters" });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
  });
});
