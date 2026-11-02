import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { RunHistoryList } from "../../src/components/history/RunHistoryList";
import { optimizationRun } from "../../src/test/fixtures";

describe("OptimizationHistory", () => {
  it("lists best gains, stop reason, reopens, and deletes optimization runs", async () => {
    const user = userEvent.setup();
    const onReopen = vi.fn();
    const onDelete = vi.fn();

    render(
      <MemoryRouter>
        <RunHistoryList
          items={[optimizationRun]}
          total={1}
          limit={10}
          offset={0}
          onOffsetChange={vi.fn()}
          onReopen={onReopen}
          onDelete={onDelete}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("GA optimization")).toBeInTheDocument();
    expect(screen.getByText("Kp:")).toBeInTheDocument();
    expect(screen.getByText("20.50")).toBeInTheDocument();
    expect(screen.getByText("stop:")).toBeInTheDocument();
    expect(screen.getByText("normal")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reopen" }));
    expect(onReopen).toHaveBeenCalledWith(optimizationRun);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(onDelete).toHaveBeenCalledWith(optimizationRun);
  });
});
