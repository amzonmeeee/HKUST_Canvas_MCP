import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { CanvasConfiguration } from "./CanvasConfiguration";

vi.mock("../api", () => ({ api: vi.fn() }));
const request = vi.mocked(api);
const profiles = [{ id: "Default", name: "Synthetic profile", selected: true }];

beforeEach(() => {
  request.mockReset();
  request.mockResolvedValue({ profiles, unlinked: false });
});

describe("Canvas unlink", () => {
  it("shows exact effects and allows cancellation without deleting anything", async () => {
    const user = userEvent.setup();
    render(<CanvasConfiguration onChanged={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Unlink Canvas profile" }),
    );
    expect(
      screen.getByText(/will not delete your Chrome profile/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      request.mock.calls.every(([, options]) => options?.method !== "DELETE"),
    ).toBe(true);
  });

  it("unlinks only after confirmation, clears selection and can explicitly reconnect", async () => {
    const user = userEvent.setup();
    const changed = vi.fn();
    render(<CanvasConfiguration onChanged={changed} />);
    await user.click(
      await screen.findByRole("button", { name: "Unlink Canvas profile" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Unlink" }),
    );
    await screen.findByText(/Canvas: Not connected/);
    expect(request).toHaveBeenCalledWith("/api/canvas/profile", {
      method: "DELETE",
    });
    expect(
      screen.getByRole("combobox", { name: "Chrome profile" }),
    ).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Connect Canvas" }),
    ).toBeDisabled();
    expect(changed).toHaveBeenCalledTimes(1);
    await user.selectOptions(screen.getByRole("combobox"), "Default");
    await user.click(screen.getByRole("button", { name: "Connect Canvas" }));
    await waitFor(() => expect(changed).toHaveBeenCalledTimes(2));
    expect(request).toHaveBeenCalledWith("/api/canvas/profile", {
      method: "PUT",
      body: { profile_id: "Default" },
    });
  });

  it("does not imply success when unlink fails", async () => {
    const user = userEvent.setup();
    const changed = vi.fn();
    render(<CanvasConfiguration onChanged={changed} />);
    await user.click(
      await screen.findByRole("button", { name: "Unlink Canvas profile" }),
    );
    request.mockRejectedValueOnce(new Error("Synthetic unlink failure"));
    await user.click(
      screen.getByRole("button", { name: "Unlink" }),
    );
    await screen.findByText("Synthetic unlink failure");
    expect(changed).not.toHaveBeenCalled();
    expect(screen.getByRole("combobox")).toHaveValue("Default");
    expect(screen.queryByText(/Canvas: Not connected/)).not.toBeInTheDocument();
  });
});
