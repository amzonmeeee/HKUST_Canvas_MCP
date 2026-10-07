import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WritePreview } from "./Actions";
import { StudyMarkdown } from "./StudyContent";
import { StudioPanel } from "./Studio";
import type { Citation, Preview } from "../types";

const citation: Citation = {
  chunk_id: "00000000-0000-4000-8000-000000000003",
  source_id: "00000000-0000-4000-8000-000000000002",
  title: "Synthetic source",
  canvas_url: null,
  locator: { page: 2 },
  excerpt: "Selected evidence",
};
const preview: Preview = {
  id: "00000000-0000-4000-8000-000000000007",
  tool: "reply_to_conversation",
  account: { user_id: "1", name: "Synthetic user" },
  target: { conversation_id: "3", recipients: ["1"] },
  payload: { body: "Exact synthetic message" },
  expires_at: "later",
  status: "pending",
};
let requests: { path: string; method: string; body?: unknown }[] = [];
beforeEach(() => {
  requests = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      requests.push({
        path,
        method: options?.method || "GET",
        body: options?.body ? JSON.parse(String(options.body)) : undefined,
      });
      if (path.endsWith("/generate"))
        return {
          status: 422,
          ok: false,
          json: async () => ({ detail: "Synthetic generation stopped" }),
        } as Response;
      const response = path.endsWith("/artifacts")
        ? { artifacts: [] }
        : path.endsWith("/notes")
          ? { notes: [] }
          : path.endsWith("/confirm")
            ? { written: true, status: "written" }
            : {};
      return { status: 200, ok: true, json: async () => response } as Response;
    }),
  );
});

describe("Study safety and controls", () => {
  it.each([
    ["Quiz", "quiz", 0, "introductory", "Introductory"],
    ["Flashcards", "flashcards", 1, "intermediate", "Intermediate"],
    ["Study guide", "study_guide", 2, "advanced", "Advanced"],
  ])(
    "submits %s and the selected slider difficulty only on generation",
    async (label, kind, step, difficulty, spokenLabel) => {
      const user = userEvent.setup();
      render(
        <StudioPanel
          workspaceId="workspace"
          sourceIds={[citation.source_id]}
          providerId="provider"
          notesVersion={0}
          openCitation={() => {}}
        />,
      );
      await user.click(await screen.findByRole("button", { name: label }));
      const slider = screen.getByRole("slider", { name: "Difficulty" });
      fireEvent.change(slider, { target: { value: String(step) } });
      expect(slider).toHaveAttribute("aria-valuetext", spokenLabel);
      expect(screen.getByRole("button", { name: label })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      expect(requests.every((r) => r.method === "GET")).toBe(true);
      await user.click(
        screen.getByRole("button", { name: "Generate material" }),
      );
      await screen.findByText("Synthetic generation stopped");
      expect(requests.find((r) => r.path.endsWith("/generate"))?.body).toEqual({
        provider_id: "provider",
        source_ids: [citation.source_id],
        kind,
        topic: "",
        count: 5,
        difficulty,
        prompt: "",
        template: "automatic",
        language: "automatic",
        orientation: "landscape",
        visual_style: "automatic",
        slide_format: "detailed",
      });
    },
  );
  it("requires a deliberate confirm click and sends only the server preview ID", async () => {
    const user = userEvent.setup();
    render(
      <WritePreview
        workspaceId="workspace"
        preview={preview}
        onFinished={() => {}}
      />,
    );
    expect(screen.getByText("Exact synthetic message")).toBeInTheDocument();
    expect(screen.getByText("Synthetic user")).toBeInTheDocument();
    expect(requests).toHaveLength(0);
    await user.click(
      screen.getByRole("button", { name: "Confirm Canvas write" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Confirm Canvas write" }),
      ).not.toBeInTheDocument(),
    );
    expect(requests).toEqual([
      {
        path: `/api/workspaces/workspace/actions/${preview.id}/confirm`,
        method: "POST",
        body: { approved: true },
      },
    ]);
  });
  it("cancels a preview without issuing a Canvas confirmation", async () => {
    const user = userEvent.setup();
    render(
      <WritePreview
        workspaceId="workspace"
        preview={preview}
        onFinished={() => {}}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Cancel action" }));
    expect(requests[0].method).toBe("DELETE");
    expect(requests.some((r) => r.path.endsWith("/confirm"))).toBe(false);
  });
  it("renders source citations as inspected local actions and discards unsafe HTML and images", async () => {
    const user = userEvent.setup(),
      open = vi.fn();
    const { container } = render(
      <StudyMarkdown
        text={`Evidence [cite:${citation.chunk_id}] <script>steal()</script> <iframe src='https://example.com'></iframe> ![remote](https://example.com/tracking.png) [bad](javascript:alert(1))`}
        citations={[citation]}
        openCitation={open}
      />,
    );
    expect(container.querySelector("script,iframe,img")).toBeNull();
    expect(container.querySelector("a[href^='javascript']")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Source 1" }));
    expect(open).toHaveBeenCalledWith(citation);
  });
  it("does not make unknown citation IDs clickable", () => {
    render(
      <StudyMarkdown
        text="Claim [cite:invented]"
        citations={[citation]}
        openCitation={() => {}}
      />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.getByText(/citation pending verification/),
    ).toBeInTheDocument();
  });
  it("keeps Studio generation disabled until there are both sources and a provider", async () => {
    render(
      <StudioPanel
        workspaceId="workspace"
        sourceIds={[]}
        providerId=""
        notesVersion={0}
        openCitation={() => {}}
      />,
    );
    expect(
      await screen.findByRole("button", { name: "Generate material" }),
    ).toBeDisabled();
    expect(requests.some((r) => r.path.endsWith("/generate"))).toBe(false);
  });
});

it("flows assistant hard-break prose while preserving code whitespace", () => {
  const { container } = render(
    <StudyMarkdown
      text={
        "First sentence.  \nSecond sentence.\n\n```text\nfirst line\nsecond line\n```"
      }
      openCitation={() => {}}
    />,
  );
  expect(container.querySelector("p")).toHaveTextContent(
    "First sentence. Second sentence.",
  );
  expect(container.querySelector("p br")).toBeNull();
  expect(container.querySelector("pre")).toHaveTextContent("first line");
  expect(container.querySelector("pre code")?.textContent).toBe(
    "first line\nsecond line\n",
  );
});
