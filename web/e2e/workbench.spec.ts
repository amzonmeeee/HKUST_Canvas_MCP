import { test, expect, type Page } from "@playwright/test";

const workspaceId = "00000000-0000-4000-8000-000000000001";
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
    else if (path === "/api/workspaces" && method === "POST") {
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
    page.getByText(/No course text is sent to an AI provider/),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe(
    "BODY",
  );
});
