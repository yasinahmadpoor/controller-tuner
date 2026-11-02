import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrajectoryChart } from "../../src/components/results/TrajectoryChart";

describe("TrajectoryChart", () => {
  it("renders with a target reference line", () => {
    render(
      <TrajectoryChart
        timePoints={[0, 0.5, 1]}
        trajectory={[1, 0.4, 0.1]}
        target={0.5}
      />,
    );

    expect(screen.getByText("System response")).toBeInTheDocument();
    expect(screen.getByText("Target reference: 0.5")).toBeInTheDocument();
    expect(screen.getByText("Target 0.5")).toBeInTheDocument();
  });
});
