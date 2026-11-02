import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProgressCharts } from "../../src/components/results/ProgressCharts";
import { optimizeResultFixture } from "../../src/test/fixtures";

describe("ProgressCharts", () => {
  it("renders cost, gain, and score history charts from a result", () => {
    render(<ProgressCharts progress={optimizeResultFixture.progress} />);

    expect(screen.getByText("Cost history")).toBeInTheDocument();
    expect(screen.getByText("Gain history")).toBeInTheDocument();
    expect(screen.getByText("Success score")).toBeInTheDocument();
  });

  it("handles missing progress history", () => {
    render(<ProgressCharts progress={{}} />);

    expect(screen.getByText("This run did not persist progress history.")).toBeInTheDocument();
  });
});
