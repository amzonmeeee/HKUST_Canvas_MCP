import { test, expect, type Page } from "@playwright/test";

const workspaceId = "00000000-0000-4000-8000-000000000001";
const sourceId = "00000000-0000-4000-8000-000000000002",
  chunkId = "00000000-0000-4000-8000-000000000003",
  providerId = "00000000-0000-4000-8000-000000000004",
  conversationId = "00000000-0000-4000-8000-000000000005",
  artifactId = "00000000-0000-4000-8000-000000000006",
  previewId = "00000000-0000-4000-8000-000000000007";
const syntheticProvider = {
  id: providerId,
  name: "Synthetic local model",
  kind: "compatible",
  model: "test-model",
  base_url: "http://127.0.0.1:11434/v1",
  has_key: false,
  credential_store: "system",
  capabilities: {
    streaming: true,
    native_tools: true,
    structured_output: false,
  },
};
const syntheticSource = {
  id: sourceId,
  workspace_id: workspaceId,
  source_key: "page:retrieval",
  kind: "page",
  title: "Retrieval notes",
  canvas_url: "https://canvas.ust.hk/courses/101/pages/retrieval",
  status: "not_synced",
  mime_type: "text/html",
  remote_updated_at: "2026-01-01",
  last_sync_at: null,
  error_message: null,
  error_code: null,
  metadata: {},
};
const syntheticCitation = {
  chunk_id: chunkId,
  source_id: sourceId,
  title: "Retrieval notes",
  canvas_url: syntheticSource.canvas_url,
  locator: { heading: "Evidence" },
  excerpt: "Retrieval searches selected evidence.",
};
const syntheticArtifact = {
  id: artifactId,
  kind: "quiz",
  title: "Retrieval practice",
  content: {
    title: "Retrieval practice",
    questions: [
      {
        type: "multiple_choice",
        question: "What does retrieval search?",
        choices: [
          "Selected evidence",
          "Browser cookies",
          "Grades",
          "Passwords",
        ],
        answer_index: 0,
        explanation: "Retrieval searches selected evidence.",
        citations: [chunkId],
      },
    ],
  },
  provenance: {
    provider_name: syntheticProvider.name,
    model: syntheticProvider.model,
    source_ids: [sourceId],
    created_at: "2026-01-01T12:00:00Z",
    prompt_version: "synthetic",
    citations: [syntheticCitation],
  },
};
const course = {
  id: "101",
  name: "Introduction to Environmental Science",
  course_code: "TEST1000 · Demo course",
  term_name: "Synthetic autumn term",
  canvas_url: "https://canvas.ust.hk/courses/101",
};
const initial = {
  id: workspaceId,
  kind: "canvas_course",
  canvas_course_id: "101",
  title: course.name,
  description: "Synthetic browser-test workspace",
  course_code: course.course_code,
  term_name: course.term_name,
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
  last_sync_at: null,
};

async function mockApi(page: Page) {
  let workspaces: Record<string, unknown>[] = [];
  let sources: Record<string, unknown>[] = [];
  let providers: Record<string, unknown>[] = [];
  let conversations: Record<string, unknown>[] = [];
  let artifacts: Record<string, unknown>[] = [];
  let notes: Record<string, unknown>[] = [];
  let messages: Record<string, unknown>[] = [];
  let previews: Record<string, unknown>[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    let result: unknown;
    if (path === "/api/session")
      result = { csrf_token: "synthetic-browser-csrf" };
    else if (path === "/api/canvas/status")
      result = {
        auth_verified: true,
        auth_status: "verified",
        profile_name: "Demo profile",
        message: "Connected.",
      };
    else if (path === "/api/canvas/courses")
      result = {
        courses: [
          course,
          {
            ...course,
            id: "102",
            name: "Data, Decisions and Society",
            course_code: "TEST2000 · Demo course",
          },
          {
            ...course,
            id: "103",
            name: "Independent Research Project",
            course_code: "TEST3000 · Demo course",
          },
        ],
        truncated: false,
      };
    else if (path === "/api/settings")
      result = {
        phase: "A",
        profile_name: "Demo profile",
        schema_version: 1,
        mcp_command: "canvas-mcp --transport stdio",
      };
    else if (path === "/api/workspaces" && method === "GET")
      result = { workspaces };
    else if (path === "/api/providers" && method === "GET")
      result = { providers };
    else if (path === "/api/providers" && method === "POST") {
      providers = [
        { ...syntheticProvider, ...request.postDataJSON(), api_key: undefined },
      ];
      result = providers[0];
    } else if (path.endsWith("/test"))
      result = { status: "connected", received_text: true };
    else if (path === `/api/workspaces/${workspaceId}/sources`)
      result = { sources };
    else if (path.endsWith("/sources/inventory")) {
      sources = [syntheticSource];
      result = { sources, warnings: [] };
    } else if (path.endsWith("/sources/sync")) {
      sources = sources.map((s) => ({
        ...s,
        status: "ready",
        last_sync_at: "2026-01-01",
      }));
      result = { sources };
    } else if (path.endsWith("/sources/text")) {
      sources = [
        {
          ...syntheticSource,
          title: request.postDataJSON().title,
          status: "ready",
          last_sync_at: "2026-01-01",
        },
      ];
      result = sources[0];
    } else if (path.endsWith(`/sources/${sourceId}`))
      result = {
        source: sources[0],
        chunks: [
          {
            id: chunkId,
            source_id: sourceId,
            text: syntheticCitation.excerpt,
            locator: syntheticCitation.locator,
          },
        ],
        total_chunks: 1,
      };
    else if (path.endsWith(`/citations/${chunkId}`))
      result = {
        id: chunkId,
        source_id: sourceId,
        text: syntheticCitation.excerpt,
        locator: syntheticCitation.locator,
      };
    else if (path.endsWith("/conversations")) result = { conversations };
    else if (path.endsWith(`/conversations/${conversationId}`))
      result = { id: conversationId, title: "Explain retrieval", messages };
    else if (path.endsWith("/chat")) {
      const prompt = request.postDataJSON().message,
        content = `Retrieval searches selected evidence. [cite:${chunkId}]`;
      conversations = [{ id: conversationId, title: prompt }];
      messages = [
        {
          id: "user-message",
          role: "user",
          content: prompt,
          status: "complete",
          citations: [],
        },
        {
          id: "00000000-0000-4000-8000-000000000010",
          role: "assistant",
          content,
          status: "complete",
          citations: [syntheticCitation],
          model: "test-model",
        },
      ];
      const events = [
        { type: "conversation", conversation_id: conversationId },
        { type: "context", chunks: [syntheticCitation] },
        { type: "text_delta", text: content },
        { type: "citation", citation: syntheticCitation },
        { type: "message_end", content, citations: [syntheticCitation] },
      ];
      await route.fulfill({
        contentType: "text/event-stream",
        body: events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""),
      });
      return;
    } else if (path.endsWith("/artifacts/generate")) {
      artifacts = [syntheticArtifact];
      result = syntheticArtifact;
    } else if (path.endsWith("/artifacts")) result = { artifacts };
    else if (path.endsWith("/notes") && method === "GET") result = { notes };
    else if (path.endsWith("/notes") && method === "POST") {
      const body = request.postDataJSON();
      const note = {
        id: "00000000-0000-4000-8000-000000000011",
        title: body.title,
        content: body.message_id ? messages[1].content : body.content,
        provenance: { citations: [syntheticCitation] },
        updated_at: "2026-01-01",
      };
      notes = [note];
      result = note;
    } else if (path.endsWith("/actions"))
      result = {
        previews,
        tools: [
          {
            name: "reply_to_conversation",
            description: "Preview reply",
            parameters: {
              properties: {
                conversation_id: { type: "string" },
                body: { type: "string" },
              },
              required: ["conversation_id", "body"],
            },
          },
        ],
      };
    else if (path.endsWith("/actions/preview")) {
      previews = [
        {
          id: previewId,
          tool: "reply_to_conversation",
          account: { name: "Synthetic user", user_id: "1" },
          target: { conversation_id: "3", recipients: ["1"] },
          payload: { body: request.postDataJSON().arguments.body },
          status: "pending",
        },
      ];
      result = { requires_human_approval: true, preview: previews[0] };
    } else if (path.endsWith(`/actions/${previewId}/confirm`)) {
      previews = [];
      result = { status: "written", written: true };
    } else if (path === "/api/workspaces" && method === "POST") {
      const body = request.postDataJSON();
      const item =
        body.kind === "custom"
          ? {
              ...initial,
              title: body.title,
              description: body.description,
              kind: "custom",
              canvas_course_id: null,
              course_code: null,
              term_name: null,
            }
          : initial;
      workspaces = [item];
      result = item;
    } else if (
      path === `/api/workspaces/${workspaceId}` &&
      method === "PATCH"
    ) {
      workspaces = [{ ...workspaces[0], ...request.postDataJSON() }];
      result = workspaces[0];
    } else if (
      path === `/api/workspaces/${workspaceId}` &&
      method === "DELETE"
    ) {
      workspaces = [];
      await route.fulfill({ status: 204 });
      return;
    } else if (path === `/api/workspaces/${workspaceId}`)
      result = workspaces[0] || initial;
    else {
      await route.fulfill({
        status: 404,
        json: { detail: "Unknown test route" },
      });
      return;
    }
    await route.fulfill({ json: result });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("desktop course navigation, local rename and explicit deletion", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/#session=synthetic-launch");
  await expect(
    page.getByRole("button", { name: "Open TEST1000 · Demo course" }),
  ).toBeVisible();
  await expect(page).not.toHaveURL(/session=/);
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-dashboard-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await expect(
    page.getByRole("heading", { name: course.name, level: 1 }),
  ).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-workspace-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Edit workspace" }).click();
  await page
    .getByRole("textbox", { name: "Workspace name" })
    .fill("Reading project");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByRole("heading", { name: "Reading project", level: 1 }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete local workspace" }).click();
  await page.getByRole("button", { name: "Keep workspace" }).click();
  await page.getByRole("button", { name: "Delete local workspace" }).click();
  await page.getByRole("button", { name: /^Delete workspace$/ }).click();
  await expect(
    page.getByRole("heading", { name: "Your study starts here." }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile custom workspace creation and stacked panels without overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/#session=synthetic-launch");
  await expect(
    page.getByRole("button", { name: "New workspace" }),
  ).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-dashboard-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "New workspace" }).click();
  await page
    .getByRole("textbox", { name: "Workspace name" })
    .fill("Research reading");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Research reading", level: 1 }),
  ).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-workspace-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sources" }).click();
  await expect(page.getByRole("button", { name: "Sources" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("settings, keyboard navigation and preserved MCP command", async ({
  page,
}) => {
  await page.goto("/#session=synthetic-launch");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.getByText("canvas-mcp --transport stdio")).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-settings-desktop.png",
    fullPage: true,
  });
  await expect(
    page.getByText(/Cloud providers receive your prompts/),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe(
    "BODY",
  );
});

test("source sync, configured streaming chat, citations, quiz practice and local notes", async ({
  page,
}) => {
  await page.goto("/#session=synthetic-launch");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Add provider" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Synthetic local model");
  await page
    .getByRole("combobox", { name: "Provider", exact: true })
    .selectOption("compatible");
  await page.getByLabel("Model identifier").fill("test-model");
  await page.getByRole("button", { name: "Save provider" }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic local model" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(
    page.getByRole("button", { name: "Connected", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page.getByRole("button", { name: "Find course sources" }).click();
  await page.getByRole("checkbox", { name: "Select Retrieval notes" }).check();
  await page.getByRole("button", { name: "Sync selected" }).click();
  await expect(page.getByText("1 selected · 1 ready")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Ask a study question" })
    .fill("Explain retrieval");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Save to notes" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Source 1", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("dialog").getByText("Retrieval searches selected evidence."),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Save to notes" }).click();
  await page.getByRole("tab", { name: /Notes/ }).click();
  await expect(
    page
      .locator(".studio-saved")
      .getByRole("button", { name: /Explain retrieval/ }),
  ).toBeVisible();
  await page.getByRole("tab", { name: /Materials/ }).click();
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(
    page.getByRole("heading", { name: "Retrieval practice" }),
  ).toBeVisible();
  await page.getByLabel("A. Selected evidence").check();
  await page.getByRole("button", { name: "Check answer" }).click();
  await expect(page.getByText("Correct", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-study-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-study-mobile.png",
    fullPage: true,
  });
});

test("Canvas writes require exact preview and a separate human confirm click", async ({
  page,
}) => {
  let writes = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/confirm")) writes++;
  });
  await page.goto("/#session=synthetic-launch");
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page
    .locator("summary")
    .filter({ hasText: "Live Canvas actions" })
    .click();
  await page
    .getByRole("combobox", { name: "Action", exact: true })
    .selectOption("reply_to_conversation");
  await page.getByLabel("conversation id *", { exact: true }).fill("3");
  await page
    .getByLabel("body *", { exact: true })
    .fill("Synthetic smoke preview");
  await page.getByRole("button", { name: "Prepare exact preview" }).click();
  await expect(page.locator(".write-preview")).toContainText(
    "Synthetic smoke preview",
  );
  await expect(page.locator(".write-preview")).toContainText("Synthetic user");
  expect(writes).toBe(0);
  await page.getByRole("button", { name: "Confirm Canvas write" }).click();
  await expect(page.locator(".write-preview")).toContainText("written");
  expect(writes).toBe(1);
  await expect(
    page.getByRole("button", { name: "Confirm Canvas write" }),
  ).not.toBeVisible();
});
