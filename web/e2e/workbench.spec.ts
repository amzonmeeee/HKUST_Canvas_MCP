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
  let profileName = "Demo profile";
  let canvasUnlinked = false;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    let result: unknown;
    if (path === "/api/session")
      result = { csrf_token: "synthetic-browser-csrf" };
    else if (path === "/api/canvas/status")
      result = {
        auth_verified: !canvasUnlinked,
        auth_status: canvasUnlinked ? "unconfigured" : "verified",
        profile_name: canvasUnlinked ? null : profileName,
        message: canvasUnlinked
          ? "Choose a profile to reconnect."
          : "Connected.",
      };
    else if (path === "/api/canvas/courses") {
      if (canvasUnlinked) {
        await route.fulfill({
          status: 409,
          json: {
            error: {
              code: "canvas_unconfigured",
              message: "Choose a profile to reconnect.",
            },
          },
        });
        return;
      }
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
    } else if (path === "/api/canvas/profiles")
      result = {
        unlinked: canvasUnlinked,
        profiles: [
          {
            id: "Default",
            name: "Demo profile",
            selected: !canvasUnlinked && profileName === "Demo profile",
          },
          {
            id: "Profile 1",
            name: "Second demo profile",
            selected: !canvasUnlinked && profileName === "Second demo profile",
          },
        ],
      };
    else if (path === "/api/canvas/profile") {
      if (method === "DELETE") {
        canvasUnlinked = true;
        previews = [];
        result = { unlinked: true, cached_data_retained: true };
      } else {
        canvasUnlinked = false;
        profileName =
          request.postDataJSON().profile_id === "Default"
            ? "Demo profile"
            : "Second demo profile";
        result = { saved: true, profile_name: profileName };
      }
    } else if (path === "/api/settings")
      result = {
        phase: "A",
        profile_name: "Demo profile",
        schema_version: 1,
        mcp_command: "canvas-mcp --transport stdio",
      };
    else if (path === "/api/workspaces" && method === "GET")
      result = { workspaces };
    else if (path === "/api/local-clients")
      result = {
        cli: [
          {
            kind: "codex",
            name: "Codex CLI",
            available: true,
            login_command: "codex login",
            mcp_command: "codex mcp add synthetic",
          },
          {
            kind: "claude_code",
            name: "Claude Code CLI",
            available: true,
            login_command: "claude auth login",
            mcp_command: "claude mcp add synthetic",
          },
        ],
        desktop: [
          { kind: "codex", name: "Codex app", available: true },
          { kind: "claude", name: "Claude Desktop", available: false },
        ],
        mcp_config: '{"mcpServers":{}}',
        can_open_login: false,
      };
    else if (path === "/api/providers/local/codex") {
      providers = [
        {
          ...syntheticProvider,
          name: "Codex CLI",
          kind: "codex",
          credential_store: "native_cli",
          capabilities: {
            streaming: true,
            native_tools: false,
            structured_output: true,
          },
        },
      ];
      result = providers[0];
    } else if (path.endsWith("/connect"))
      result = { connected: true, restart_required: true };
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
      sources = [
        syntheticSource,
        {
          ...syntheticSource,
          id: "00000000-0000-4000-8000-000000000012",
          source_key: "file:reading",
          kind: "file",
          title: "Reading handout",
        },
        {
          ...syntheticSource,
          id: "00000000-0000-4000-8000-000000000013",
          source_key: "external:video",
          kind: "external",
          title: "Video reference",
          status: "external_reference",
        },
      ];
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
        display_html:
          '<h2>Assignment instructions</h2><p>A <strong>complete</strong> paragraph.</p><ol><li>First requirement</li><li>Second requirement</li></ol><table><tr><th>Criterion</th><td>Evidence</td></tr></table><p style="text-align:center">Centered text</p>',
      };
    else if (path.endsWith(`/citations/${chunkId}`))
      result = {
        id: chunkId,
        source_id: sourceId,
        text: syntheticCitation.excerpt,
        locator: syntheticCitation.locator,
      };
    else if (
      path.includes("/temporary-conversations/") &&
      path.endsWith("/save")
    ) {
      conversations = [{ id: conversationId, title: "Saved temporary chat" }];
      result = { ...conversations[0], messages };
    } else if (path.endsWith("/conversations")) result = { conversations };
    else if (path.endsWith(`/conversations/${conversationId}`))
      result = { id: conversationId, title: "Explain retrieval", messages };
    else if (path.endsWith("/chat")) {
      const prompt = request.postDataJSON().message,
        content = `Retrieval searches selected evidence. [cite:${chunkId}]`;
      if (!request.postDataJSON().temporary)
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

test("Canvas unlink confirms, keeps a workspace and requires explicit reconnect", async ({
  page,
}) => {
  await page.goto("/#session=synthetic-launch");
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Unlink Canvas profile" }).click();
  await expect(
    page.getByText(/will not delete your Chrome profile/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("combobox", { name: "Chrome profile" }),
  ).toHaveValue("Default");
  await page.getByRole("button", { name: "Unlink Canvas profile" }).click();
  await page.getByRole("button", { name: "Unlink", exact: true }).click();
  await expect(page.getByText(/Canvas: Not connected/)).toBeVisible();
  await expect(
    page
      .locator(".canvas-config-form")
      .getByRole("button", { name: "Connect Canvas" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(
    page.getByText("Canvas: Not connected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "My workspaces 1" }).getByText(course.name, { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Configure Canvas" }).click();
  await expect(
    page.getByRole("combobox", { name: "Chrome profile" }),
  ).toHaveValue("");
  await page
    .getByRole("combobox", { name: "Chrome profile" })
    .selectOption("Profile 1");
  await page
    .getByRole("button", { name: "Connect Canvas", exact: true })
    .click();
  await expect(
    page.getByText("Canvas connected", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Chrome · Second demo profile")).toBeVisible();
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
  await page.getByRole("button", { name: "Delete workspace…" }).click();
  await page.getByRole("button", { name: "Keep workspace" }).click();
  await page.getByRole("button", { name: "Delete workspace…" }).click();
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
  await page.getByRole("button", { name: "Add API or local server" }).click();
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
    .getByRole("button", { name: "Reply to Inbox conversation", exact: true })
    .click();
  expect(writes).toBe(0);
  await expect(page.getByRole("combobox", { name: "Action" })).toHaveCount(0);
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

test("existing CLI login and desktop connection are usable at both screen sizes", async ({
  page,
}) => {
  await page.goto("/#session=synthetic-launch");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const codex = page.locator(".local-client-row").filter({
    has: page.getByRole("heading", { name: "Codex CLI", exact: true }),
  });
  await codex.getByRole("button", { name: "Use existing login" }).click();
  await expect(
    page
      .locator(".provider-row")
      .getByText("Uses your CLI login", { exact: false }),
  ).toBeVisible();
  const desktop = page.locator(".local-client-row").filter({
    has: page.getByRole("heading", { name: "Codex app", exact: true }),
  });
  await desktop.getByRole("button", { name: "Connect Canvas" }).click();
  await expect(page.getByText(/Canvas MCP connected/)).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-native-settings-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-native-settings-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("workspace fills wide screens and remembers pointer and keyboard panel sizes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 2560, height: 1440 });
  await page.goto("/#session=synthetic-launch");
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  const sourceDivider = page.getByRole("separator", {
    name: "Resize Sources and Conversation",
  });
  const studioDivider = page.getByRole("separator", {
    name: "Resize Conversation and Study Studio",
  });
  await expect(sourceDivider).toBeVisible();
  await expect(studioDivider).toBeVisible();
  const bounds = await page.locator(".workbench").boundingBox();
  const main = await page.locator(".main-content").boundingBox();
  expect(bounds!.width).toBeGreaterThan(2200);
  expect(
    Math.abs(
      bounds!.x - main!.x - (main!.x + main!.width - bounds!.x - bounds!.width),
    ),
  ).toBeLessThan(2);
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-layout-wide.png",
    fullPage: true,
  });
  const sourceBefore = Number(
    await sourceDivider.getAttribute("aria-valuenow"),
  );
  await sourceDivider.focus();
  await page.keyboard.press("ArrowRight");
  await expect(sourceDivider).toHaveAttribute(
    "aria-valuenow",
    String(sourceBefore + 24),
  );
  const studioBefore = Number(
    await studioDivider.getAttribute("aria-valuenow"),
  );
  await studioDivider.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(studioDivider).toHaveAttribute(
    "aria-valuenow",
    String(studioBefore + 24),
  );
  const handle = (await sourceDivider.boundingBox())!;
  await page.mouse.move(handle.x + handle.width / 2, handle.y + 80);
  await page.mouse.down();
  await page.mouse.move(handle.x + handle.width / 2 + 96, handle.y + 80, {
    steps: 6,
  });
  await page.mouse.up();
  await expect(sourceDivider).toHaveAttribute(
    "aria-valuenow",
    String(sourceBefore + 120),
  );
  await page.reload();
  await expect(sourceDivider).toHaveAttribute(
    "aria-valuenow",
    String(sourceBefore + 120),
  );
  await expect(studioDivider).toHaveAttribute(
    "aria-valuenow",
    String(studioBefore + 24),
  );
  await page.getByRole("button", { name: "Sources", exact: true }).click();
  await expect(sourceDivider).toBeHidden();
  await page.getByRole("button", { name: "Sources", exact: true }).click();
  await expect(sourceDivider).toHaveAttribute(
    "aria-valuenow",
    String(sourceBefore + 120),
  );
  await page.getByRole("button", { name: "Study Studio", exact: true }).click();
  await expect(studioDivider).toBeHidden();
  await page.getByRole("button", { name: "Study Studio", exact: true }).click();
  await expect(studioDivider).toBeVisible();
  await page.getByRole("button", { name: "Study Studio", exact: true }).click();
  await page.getByRole("button", { name: "Sources", exact: true }).click();
  expect(
    (await page.locator(".chat-panel").boundingBox())!.width,
  ).toBeGreaterThan(2000);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Sources", exact: true }).click();
  await page.getByRole("button", { name: "Study Studio", exact: true }).click();
  await studioDivider.press("Home");
  await expect(studioDivider).toHaveAttribute("aria-valuenow", "280");
  await sourceDivider.press("End");
  expect(
    (await page.locator(".chat-panel").boundingBox())!.width,
  ).toBeGreaterThanOrEqual(359);
  await sourceDivider.dblclick();
  await expect(sourceDivider).toHaveAttribute(
    "aria-valuenow",
    String(sourceBefore),
  );
  await expect(studioDivider).toHaveAttribute(
    "aria-valuenow",
    String(studioBefore),
  );
  await page.getByRole("button", { name: "Flashcards", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Flashcards", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const difficulty = page.getByRole("slider", { name: "Difficulty" });
  await difficulty.press("End");
  await expect(difficulty).toHaveAttribute("aria-valuetext", "Advanced");
  await difficulty.press("Home");
  await expect(difficulty).toHaveAttribute("aria-valuetext", "Introductory");
  for (const width of [1440, 1200, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
    if (width < 1200) await expect(page.getByRole("separator")).toHaveCount(0);
    else await expect(sourceDivider).toBeVisible();
  }
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-layout-mobile.png",
    fullPage: true,
  });
});

test("dashboard views, direct profile configuration and source-wide/category selection", async ({
  page,
}) => {
  // Match the installed server's CSP, including DOMParser's treatment of styles.
  await page.route("**/*", async (route) => {
    if (route.request().resourceType() !== "document") return route.fallback();
    const response = await route.fetch();
    await route.fulfill({
      response,
      headers: {
        ...response.headers(),
        "Content-Security-Policy":
          "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; " +
          "img-src 'self' data:; connect-src 'self'; object-src 'none'; " +
          "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
      },
    });
  });
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/#session=synthetic-launch");
  await page.getByRole("button", { name: "Card view", exact: true }).click();
  await expect(page.locator(".course-board")).toHaveClass(/card-view/);
  await page.getByRole("button", { name: "Configure Canvas" }).click();
  await page
    .getByRole("combobox", { name: "Chrome profile" })
    .selectOption("Profile 1");
  await page.getByRole("button", { name: "Save Canvas profile" }).click();
  await expect(page.getByText("Chrome · Second demo profile")).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-cards.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("combobox", { name: "Chrome profile" }),
  ).toHaveValue("Profile 1");
  const settings = (await page.locator(".settings-content").boundingBox())!;
  const main = (await page.locator(".main-content").boundingBox())!;
  expect(settings.width).toBeGreaterThan(main.width - 100);
  await page
    .getByRole("combobox", { name: "Chrome profile" })
    .selectOption("Default");
  await page.getByRole("button", { name: "Save Canvas profile" }).click();
  await expect(page.getByText("Canvas profile saved.")).toBeVisible();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Card view", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page.getByRole("button", { name: "Find course sources" }).click();
  await page.getByRole("button", { name: "Select all", exact: true }).click();
  await expect(page.getByText("2 selected · 0 ready")).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Select Video reference" }),
  ).not.toBeChecked();
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await page
    .getByRole("button", { name: "Select category page", exact: true })
    .click();
  await expect(page.getByText("1 selected · 0 ready")).toBeVisible();
  await expect(
    page.getByRole("checkbox", { name: "Select Reading handout" }),
  ).not.toBeChecked();
  await page.getByRole("button", { name: "Sync selected" }).click();
  await page.getByRole("button", { name: /Retrieval notes ready/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Assignment instructions" }),
  ).toBeVisible();
  await expect(dialog.locator("ol li")).toHaveCount(2);
  await expect(dialog.getByRole("table")).toContainText("Criterion");
  await expect(dialog.getByText("Text excerpt")).toHaveCount(0);
  expect(
    await dialog
      .getByText("Centered text")
      .evaluate((el) => getComputedStyle(el).textAlign),
  ).toBe("center");
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-source-reading.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
});

test("Return shortcuts preserve newlines, respect IME and keep conversation controls/content aligned", async ({
  page,
}) => {
  await page.setViewportSize({ width: 2560, height: 1200 });
  await page.goto("/#session=synthetic-launch");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .locator(".local-client-row")
    .filter({
      has: page.getByRole("heading", { name: "Codex CLI", exact: true }),
    })
    .getByRole("button", { name: "Use existing login" })
    .click();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  let sends = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/chat")) sends++;
  });
  const prompt = page.getByRole("textbox", { name: "Ask a study question" });
  await prompt.fill("First line");
  await prompt.press("Enter");
  await expect(prompt).toHaveValue("First line\n");
  expect(sends).toBe(0);
  await prompt.press("Control+Enter");
  await expect(
    page.getByRole("button", { name: "Save to notes" }),
  ).toBeVisible();
  expect(sends).toBe(1);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Send shortcut" })
    .selectOption("enter");
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await prompt.fill("Second line");
  await prompt.press("Meta+Enter");
  await expect(prompt).toHaveValue("Second line\n");
  await prompt.evaluate((element) =>
    element.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        code: "Enter",
        isComposing: true,
        bubbles: true,
      }),
    ),
  );
  expect(sends).toBe(1);
  await prompt.press("Enter");
  await expect.poll(() => sends).toBe(2);
  await expect(
    page.getByRole("button", { name: "Send", exact: true }),
  ).toBeVisible();
  const provider = (await page
    .getByRole("combobox", { name: "Provider", exact: true })
    .boundingBox())!;
  const history = (await page
    .getByRole("combobox", { name: "Conversation history" })
    .boundingBox())!;
  expect(Math.abs(provider.y - history.y)).toBeLessThan(8);
  const message = page.locator(".chat-message.assistant").last();
  const body = (await message.locator(".study-markdown").boundingBox())!;
  const box = (await message.boundingBox())!;
  expect(Math.abs(body.width - box.width)).toBeLessThan(3);
  await prompt.focus();
  expect(await prompt.evaluate((el) => getComputedStyle(el).outlineColor)).toBe(
    "rgb(0, 90, 156)",
  );
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-chat-toolbar.png",
    fullPage: true,
  });
  await page.reload();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("combobox", { name: "Send shortcut" }),
  ).toHaveValue("enter");
});

test("Studio Word/Excel choices send instructions and template, then offer real export routes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto("/#session=synthetic-launch");
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page.getByRole("button", { name: "Find course sources" }).click();
  await page.getByRole("checkbox", { name: "Select Retrieval notes" }).check();
  await page.getByRole("button", { name: "Sync selected" }).click();
  await page.getByRole("button", { name: "Word", exact: true }).click();
  await page
    .getByRole("combobox", { name: /Document template/ })
    .selectOption("revision_outline");
  await page
    .getByRole("textbox", { name: "Instructions" })
    .fill("Use Chinese and emphasize definitions.");
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-word-controls.png",
    fullPage: true,
  });
  // Supply a synthetic provider and document response without a paid model call.
  await page.route("**/api/providers", (route) =>
    route.fulfill({ json: { providers: [syntheticProvider] } }),
  );
  await page.reload();
  await page.getByRole("button", { name: "Word", exact: true }).click();
  await page.getByRole("checkbox", { name: "Select Retrieval notes" }).check();
  await page
    .getByRole("combobox", { name: /Document template/ })
    .selectOption("revision_outline");
  await page
    .getByRole("textbox", { name: "Instructions" })
    .fill("Use Chinese and emphasize definitions.");
  await page.route("**/artifacts/generate", async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.prompt).toBe("Use Chinese and emphasize definitions.");
    const artifact = {
      ...syntheticArtifact,
      kind: payload.kind,
      content:
        payload.kind === "document"
          ? {
              title: "Retrieval practice",
              template: payload.template,
              sections: [
                {
                  heading: "Evidence",
                  body: "Source-grounded text",
                  citations: [chunkId],
                },
              ],
            }
          : {
              title: "Retrieval practice",
              columns: ["Concept", "Meaning"],
              rows: [
                {
                  cells: ["Retrieval", "Evidence search"],
                  citations: [chunkId],
                },
              ],
            },
    };
    await route.fulfill({ json: artifact });
  });
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(
    page.getByRole("link", { name: "Word (.docx)" }),
  ).toHaveAttribute("href", /format=docx&template=revision_outline/);
  await expect(page.getByText("Source-grounded text")).toBeVisible();
  await page.getByRole("button", { name: "Back to materials" }).click();
  await page.getByRole("button", { name: "Excel", exact: true }).click();
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(page.locator(".studio-table")).toContainText("Evidence search");
  await expect(
    page.getByRole("link", { name: "Excel (.xlsx)" }),
  ).toHaveAttribute("href", /format=xlsx/);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-excel-mobile.png",
    fullPage: true,
  });
});

test("archive/restore and temporary chat saved partway through are explicit", async ({
  page,
}) => {
  await page.goto("/#session=synthetic-launch");
  await page.route("**/api/providers", (route) =>
    route.fulfill({ json: { providers: [syntheticProvider] } }),
  );
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page
    .getByRole("button", { name: "Temporary chat", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "Send shortcut" }),
  ).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Ask a study question" })
    .fill("Keep this temporary exchange");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Save chat", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Save to notes", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("combobox", { name: "Conversation history" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Save chat", exact: true }).click();
  await expect(
    page.getByText("Chat saved to conversation history."),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Conversation history" }),
  ).toHaveValue(conversationId);
  await expect(
    page.getByRole("button", { name: "Save to notes", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Archive workspace", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /My workspaces/ }),
  ).toBeVisible();
  await expect(page.locator(".workspace-row")).toHaveCount(0);
  await page.getByRole("button", { name: "Archived (1)", exact: true }).click();
  await expect(page.locator(".workspace-row")).toHaveCount(1);
  await page.locator(".workspace-row").click();
  await page
    .getByRole("button", { name: "Restore workspace", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Archive workspace", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(page.locator(".workspace-row")).toHaveCount(1);
});

test("visual Studio previews, exports and responsive prose use real container widths", async ({
  page,
}) => {
  await page.setViewportSize({ width: 3440, height: 1440 });
  await page.goto("/#session=synthetic-launch");
  await expect(page.locator(".workbench-logo")).toBeVisible();
  const favicon = await page.locator('link[rel="icon"]').getAttribute("href");
  expect(favicon).toMatch(/canvas-mark.*\.svg/);
  await page.route("**/api/providers", (route) =>
    route.fulfill({ json: { providers: [syntheticProvider] } }),
  );
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const description = page.getByText(/Use a signed-in CLI, an official API/);
  expect(
    await description.evaluate((el) => getComputedStyle(el).maxWidth),
  ).toBe("none");
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-new-settings-wide.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page
    .getByRole("button", { name: "Open TEST1000 · Demo course" })
    .click();
  await page.getByRole("button", { name: "Find course sources" }).click();
  await page
    .getByRole("button", { name: "Select category page", exact: true })
    .click();
  const summary = page
    .locator(".source-group summary")
    .filter({ hasText: "Pages" });
  const category = page.getByRole("button", {
    name: "Clear category page",
    exact: true,
  });
  expect((await category.boundingBox())!.x).toBeGreaterThan(
    (await summary.boundingBox())!.x + 50,
  );
  await page.getByRole("button", { name: "Sync selected" }).click();
  await page.route("**/artifacts/generate", (route) => {
    const payload = route.request().postDataJSON();
    const content =
      payload.kind === "mindmap"
        ? {
            title: "Evidence map",
            nodes: [
              {
                id: "evidence",
                parent_id: null,
                label: "Evidence",
                body: "Search selected sources.",
                citations: [chunkId],
              },
              {
                id: "citation",
                parent_id: "evidence",
                label: "Citations",
                body: "Verify each excerpt.",
                citations: [chunkId],
              },
            ],
          }
        : payload.kind === "slides"
          ? {
              title: "Evidence slides",
              slides: [
                {
                  heading: "Finding evidence",
                  body: "Search the selected sources.",
                  bullets: ["Retrieve", "Verify"],
                  notes: "Explain how evidence is selected.",
                  citations: [chunkId],
                },
                {
                  heading: "Citing sources",
                  body: "Keep citations verifiable.",
                  bullets: ["Inspect excerpts"],
                  notes: "Open citations to inspect original text.",
                  citations: [chunkId],
                },
              ],
            }
          : {
              title: "Evidence infographic",
              sections: [
                {
                  heading: "Evidence",
                  body: "Ground explanations in selected sources.",
                  stat: "",
                  citations: [chunkId],
                },
                {
                  heading: "Verification",
                  body: "Inspect the original excerpt before relying on an answer.",
                  stat: "",
                  citations: [chunkId],
                },
              ],
            };
    return route.fulfill({
      json: {
        ...syntheticArtifact,
        kind: payload.kind,
        content,
        provenance: {
          ...syntheticArtifact.provenance,
          orientation: payload.orientation,
          visual_style: payload.visual_style,
        },
      },
    });
  });
  await page.getByRole("button", { name: "Mind map", exact: true }).click();
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(page.locator(".mindmap-tree").first()).toContainText(
    "Citations",
  );
  await expect(
    page.getByRole("link", { name: "SVG", exact: true }),
  ).toHaveAttribute("href", /format=svg/);
  await page.getByRole("button", { name: "Expand preview" }).click();
  await expect(page.locator(".visual-material-dialog")).toBeVisible();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-map-wide.png",
    fullPage: true,
  });
  await page
    .locator(".visual-material-dialog")
    .getByRole("button", { name: /Retrieval notes/ })
    .first()
    .click();
  await expect(page.locator(".visual-material-dialog")).toBeHidden();
  await expect(page.locator(".source-dialog")).toBeVisible();
  await page.getByRole("button", { name: "Close source", exact: true }).click();
  await page.getByRole("button", { name: "Back to materials" }).click();
  await page.getByRole("button", { name: "Slides", exact: true }).click();
  await page.getByRole("button", { name: /Presenter slides/ }).click();
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(
    page.getByRole("link", { name: "PowerPoint (.pptx)" }),
  ).toHaveAttribute("href", /format=pptx/);
  await page
    .getByRole("button", { name: "Next slide", exact: true })
    .first()
    .click();
  await expect(page.locator(".slides-preview").first()).toContainText(
    "Slide 2 of 2",
  );
  await page.getByRole("button", { name: "Expand preview" }).click();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-slides-wide.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Close material preview" }).click();
  await page.getByRole("button", { name: "Back to materials" }).click();
  await page.getByRole("button", { name: "Infographic", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Language", exact: true })
    .selectOption("zh-Hant");
  await page.getByRole("button", { name: "portrait", exact: true }).click();
  await page.getByRole("button", { name: "notebook", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Instructions" })
    .fill("Use a clear sequence and source-backed statements.");
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(page.locator(".infographic-preview").first()).toHaveClass(
    /orientation-portrait visual-notebook/,
  );
  await page.getByRole("button", { name: "Expand preview" }).click();
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-infographic-wide.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Close material preview" }).click();
  await page
    .getByRole("textbox", { name: "Ask a study question" })
    .fill("Check wrapping");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.locator(".chat-message.assistant .study-markdown"),
  ).toBeVisible();
  expect(
    await page
      .locator(".chat-message.assistant .study-markdown p")
      .evaluate((el) => getComputedStyle(el).maxWidth),
  ).toBe("none");
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-workspace-wide.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-workspace-new-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  expect((await description.boundingBox())!.height).toBeGreaterThan(40);
  await page.screenshot({
    path: "/private/tmp/hkust-canvas-v3-settings-new-mobile.png",
    fullPage: true,
  });
});
