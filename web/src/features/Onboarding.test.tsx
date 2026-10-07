import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { api } from "../api";
import { Onboarding } from "./Onboarding";
vi.mock("../api", () => ({
  api: vi.fn().mockResolvedValue({ completed: true }),
}));
vi.mock("./CanvasConfiguration", () => ({
  CanvasConfiguration: () => <p>Profile configuration</p>,
}));
vi.mock("./Providers", () => ({
  ProviderSettings: () => <p>Provider configuration</p>,
}));
vi.mock("./LocalClients", () => ({
  LocalClients: () => <p>Optional MCP configuration</p>,
}));
it("allows skips, requires safety acknowledgement and saves completion", async () => {
  const user = userEvent.setup();
  const complete = vi.fn();
  render(<Onboarding onComplete={complete} />);
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(
    screen.getByRole("button", { name: "Continue / skip for now" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Continue / skip for now" }),
  );
  expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(
    screen.getByRole("button", { name: "Continue / skip for now" }),
  );
  await user.click(screen.getByRole("button", { name: "Open workbench" }));
  expect(api).toHaveBeenCalledWith("/api/onboarding", {
    method: "PUT",
    body: { privacy_acknowledged: true },
  });
  expect(complete).toHaveBeenCalledOnce();
});
