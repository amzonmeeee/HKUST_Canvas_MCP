import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RecordingTranscription } from "./Recording";
import type { Source, TranscriberStatus } from "../types";

const source: Source = {
  id: "00000000-0000-4000-8000-000000000011",
  workspace_id: "00000000-0000-4000-8000-000000000001",
  source_key: "recording:comp1000-l1-2026-09-01-09-00",
  kind: "recording",
  title: "COMP1000-L1-2026-09-01-09-00",
  canvas_url: null,
  status: "not_synced",
  mime_type: null,
  last_sync_at: null,
  remote_updated_at: null,
  error_message: null,
  error_code: null,
  metadata: {},
};
let status: TranscriberStatus;
let requests: { path: string; method: string; body?: unknown }[];

beforeEach(() => {
  requests = [];
  status = { installed: false, model: null, component_commit: null, disk_bytes: 0, job: null };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      const method = options?.method || "GET";
      requests.push({
        path,
        method,
        body: options?.body ? JSON.parse(String(options.body)) : undefined,
      });
      const body =
        path === "/api/session" ? { csrf_token: "synthetic" } : method === "GET" ? status : {};
      return { status: 200, ok: true, json: async () => body } as Response;
    }),
  );
});

describe("RVC recording transcription", () => {
  it("offers an explicit install with the download size before any download", async () => {
    render(<RecordingTranscription workspaceId="w" source={source} onTranscribed={() => {}} />);
    expect(await screen.findByText(/4–5 GB/)).toBeInTheDocument();
    expect(requests.some((r) => r.method === "POST")).toBe(false);
    await userEvent.selectOptions(screen.getByLabelText("Speech model"), "qwen3-asr-0.6b");
    await userEvent.click(screen.getByRole("button", { name: /Install transcriber/ }));
    await waitFor(() =>
      expect(requests).toContainEqual({
        path: "/api/transcriber/install",
        method: "POST",
        body: { model: "qwen3-asr-0.6b" },
      }),
    );
  });

  it("transcribes when installed and reports a finished transcript once", async () => {
    status = { installed: true, model: "qwen3-asr-1.7b", component_commit: "x", disk_bytes: 5 * 1024 ** 3, job: null };
    const done = vi.fn();
    render(<RecordingTranscription workspaceId="w" source={source} onTranscribed={done} />);
    await userEvent.click(await screen.findByRole("button", { name: /^Transcribe$/ }));
    expect(requests).toContainEqual({
      path: `/api/workspaces/w/sources/${source.id}/transcribe`,
      method: "POST",
      body: undefined,
    });
    expect(screen.getByRole("button", { name: /Remove transcriber \(5.0 GB\)/ })).toBeInTheDocument();
    status = {
      ...status,
      job: { kind: "transcribe", state: "complete", event: "complete", message: null, source_id: source.id },
    };
    await userEvent.click(screen.getByRole("button", { name: /^Transcribe$/ }));
    await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  });
});
