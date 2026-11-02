import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useJobEvents } from "../../src/hooks/useJobEvents";

class FakeEventSource {
  static last: FakeEventSource | null = null;
  listeners = new Map<string, (event: MessageEvent<string>) => void>();
  onerror: (() => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener as (event: MessageEvent<string>) => void);
  }

  removeEventListener(type: string) {
    this.listeners.delete(type);
  }

  emit(type: string, data: unknown) {
    this.listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent<string>);
  }

  close() {
    this.closed = true;
  }
}

describe("useJobEvents", () => {
  const original = globalThis.EventSource;

  afterEach(() => {
    globalThis.EventSource = original;
  });

  it("parses progress events and terminal events", () => {
    globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
    const { result } = renderHook(() => useJobEvents("job-1"));

    act(() => FakeEventSource.last?.emit("progress", { generation: 3 }));
    expect(result.current.progress).toEqual({ generation: 3 });

    act(() => FakeEventSource.last?.emit("done", { status: "succeeded" }));
    expect(result.current.terminal).toBe("succeeded");
    expect(FakeEventSource.last?.closed).toBe(true);
  });

  it("falls back to polling when the stream errors", () => {
    globalThis.EventSource = FakeEventSource as unknown as typeof EventSource;
    const { result } = renderHook(() => useJobEvents("job-1"));

    act(() => FakeEventSource.last?.onerror?.());

    expect(result.current.fallback).toBe(true);
    expect(FakeEventSource.last?.closed).toBe(true);
  });

  it("falls back when EventSource is unavailable", () => {
    // @ts-expect-error simulate an unsupported browser
    delete globalThis.EventSource;
    const { result } = renderHook(() => useJobEvents("job-1"));
    expect(result.current.fallback).toBe(true);
  });
});
