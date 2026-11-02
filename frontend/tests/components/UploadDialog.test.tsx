import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { UploadSystemDialog } from "../../src/components/catalog/UploadSystemDialog";
import { renderWithProviders } from "../../src/test/utils";

describe("UploadSystemDialog", () => {
  it("rejects non-Python files", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<UploadSystemDialog onClose={vi.fn()} onCreated={vi.fn()} />);

    const input = screen.getByLabelText("Choose file");
    await user.upload(input, new File(["hello"], "notes.txt", { type: "text/plain" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only .py files are supported.",
    );
  });

  it("accepts a .py file", async () => {
    const user = userEvent.setup();
    renderWithProviders(<UploadSystemDialog onClose={vi.fn()} onCreated={vi.fn()} />);

    const input = screen.getByLabelText("Choose file");
    await user.upload(input, new File(["def dynamics(): pass"], "plant.py", { type: "text/x-python" }));

    expect(await screen.findByText("plant.py")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
