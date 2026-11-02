import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { RunHistoryList } from "../../src/components/history/RunHistoryList";
import { simulationRun } from "../../src/test/fixtures";

describe("RunHistoryList", () => {
  it("explains that empty history is scoped to the workspace", () => {
    render(
      <MemoryRouter>
        <RunHistoryList
          items={[]}
          total={0}
          limit={10}
          offset={0}
          onOffsetChange={vi.fn()}
          onDelete={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("No runs in this workspace")).toBeInTheDocument();
    expect(screen.getByText(/optimization runs are listed under the Optimizations toggle/i)).toBeInTheDocument();
  });

  it("paginates, reopens, and deletes a run after confirmation", async () => {
    const user = userEvent.setup();
    const onOffsetChange = vi.fn();
    const onReopen = vi.fn();
    const onDelete = vi.fn();

    render(
      <MemoryRouter>
        <RunHistoryList
          items={[simulationRun]}
          total={25}
          limit={10}
          offset={0}
          onOffsetChange={onOffsetChange}
          onReopen={onReopen}
          onDelete={onDelete}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Showing 1–10 of 25")).toBeInTheDocument();
    expect(screen.getByText("PID")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(onOffsetChange).toHaveBeenCalledWith(10);

    await user.click(screen.getByRole("button", { name: "Reopen" }));
    expect(onReopen).toHaveBeenCalledWith(simulationRun);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(onDelete).toHaveBeenCalledWith(simulationRun);
  });
});
