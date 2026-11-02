import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AutoTuneResults } from "../../src/components/results/AutoTuneResults";
import { optimizeResultFixture, systemFixture } from "../../src/test/fixtures";

describe("AutoTuneResults", () => {
  it("renders gains, metrics versus targets, and stop reason", () => {
    render(
      <AutoTuneResults
        result={optimizeResultFixture}
        targets={systemFixture.optimization.fixed_targets}
      />,
    );

    expect(screen.getByText("Best gains")).toBeInTheDocument();
    expect(screen.getByText("20.5932")).toBeInTheDocument();
    expect(screen.getByText("0.2998")).toBeInTheDocument();
    expect(screen.getByText("9.6994")).toBeInTheDocument();
    expect(screen.getByText("Normal")).toBeInTheDocument();
    expect(
      screen.getByText("Completed the configured number of generations."),
    ).toBeInTheDocument();
    expect(screen.getByText("Achieved vs targets")).toBeInTheDocument();
    expect(screen.getAllByText("Hit").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Miss").length).toBeGreaterThan(0);
    expect(screen.getByText(/run_id/)).toHaveTextContent(optimizeResultFixture.run_id);
  });
});
