import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { DeleteWorkspaceDialog } from "../../src/components/common/DeleteWorkspaceDialog";
import { systemFixture } from "../../src/test/fixtures";
import { server } from "../../src/test/server";
import { renderWithProviders } from "../../src/test/utils";

describe("DeleteWorkspaceDialog", () => {
  it("requires explicit confirmation before deleting", async () => {
    const user = userEvent.setup();
    const onDeleted = vi.fn();
    const onClose = vi.fn();
    let deletedId: string | null = null;
    server.use(
      http.delete("*/api/v1/systems/*", ({ request }) => {
        deletedId = new URL(request.url).pathname.split("/").pop() ?? null;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(
      <DeleteWorkspaceDialog
        workspace={systemFixture}
        onClose={onClose}
        onDeleted={onDeleted}
      />,
    );

    expect(screen.getByRole("alertdialog")).toHaveTextContent(systemFixture.system_id);
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(onDeleted).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Delete workspace permanently" }));

    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(systemFixture));
    expect(deletedId).toBe(systemFixture.system_id);
  });

  it("shows active-job errors from the backend", async () => {
    const user = userEvent.setup();
    server.use(
      http.delete("*/api/v1/systems/*", () =>
        HttpResponse.json(
          { error: { code: "system_in_use", message: "system has an active optimization job" } },
          { status: 409 },
        ),
      ),
    );

    renderWithProviders(
      <DeleteWorkspaceDialog
        workspace={systemFixture}
        onClose={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Delete workspace permanently" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "system has an active optimization job",
    );
  });
});
