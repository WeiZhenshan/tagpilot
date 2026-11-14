import { test, expect } from "@playwright/test";

// 合成数据只验证交互反馈（按下、等待、乐观状态），不调用真实模型或业务接口。
const plan = {
  revision: 1,
  hash: "fixture-hash",
  valid: true,
  build_id: "fixture-build",
  snapshot_id: "fixture-snapshot",
  tree: {
    logic: "AND",
    children: [
      {
        clause_id: "a",
        source_span: "近30天异名跨行转入超过50万元",
        tag_id: 1,
        name: "近30天异名跨行转入金额",
        operator: ">",
        values: ["500000"],
        unit: "CNY",
        value_unit: "CNY",
        value_scale: "1",
        status: "BOUND",
        allowed_operators: [">"],
        definition: "合成测试条件。",
      },
    ],
  },
};

const makeThread = (id: string, title: string) => ({
  thread_id: id,
  title,
  library_id: 107,
  archived: false,
  status: "COMPLETED" as const,
  revision: 1,
  plan: structuredClone(plan),
  versions: [structuredClone(plan)],
  messages: [
    { id: `${id}-u`, role: "user", text: "近30天转入客户", created_at: "2026-09-21T01:00:00Z" },
    { id: `${id}-a`, role: "assistant", text: "圈选方案已生成，可以核对条件并统计人数。", created_at: "2026-09-21T01:00:05Z" },
  ],
  events: [],
  capabilities: { count: true, create: true, preview: true },
});

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function setup(page: import("@playwright/test").Page, options: { threadDelay?: number; countDelay?: number; runDelay?: number; runWithoutReply?: boolean } = {}) {
  let t1: any = makeThread("t1", "第一个会话");
  const t2 = makeThread("t2", "第二个会话");
  await page.route("**/dev-api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (path.endsWith("/getInfo")) return route.fulfill({ json: { code: 200, user: { userId: 2, userName: "demo", nickName: "测试用户" } } });
    if (path.endsWith("/library/list")) return route.fulfill({ json: { code: 200, rows: [{ libraryId: 107, libraryName: "个人客户经营标签库" }] } });
    if (path.endsWith("/tags/tree")) return route.fulfill({ json: { code: 200, data: [] } });
    if (path.endsWith("/threads") && method === "GET") {
      return route.fulfill({ json: { code: 200, data: [t1, t2].map((t) => ({
        threadId: t.thread_id, title: t.title, libraryId: 107, archived: "0", pinned: "0", updateTime: "2026-09-21 09:00:00",
      })) } });
    }
    if (path.endsWith("/threads/t2") && method === "GET") {
      await delay(options.threadDelay ?? 600);
      return route.fulfill({ json: { code: 200, data: t2 } });
    }
    if (path.endsWith("/threads/t1") && method === "GET") return route.fulfill({ json: { code: 200, data: t1 } });
    if (path.endsWith("/events")) {
      return route.fulfill({ contentType: "text/event-stream", body: `event: state\ndata: ${JSON.stringify(t1)}\n\n` });
    }
    if (path.endsWith("/count")) {
      await delay(options.countDelay ?? 600);
      t1 = { ...t1, count: { value: 1268, revision: t1.revision, executed_at: "2026-09-21T01:05:00Z", data_as_of: "2026-09-30" } };
      return route.fulfill({ json: { code: 200, data: t1 } });
    }
    if (path.endsWith("/runs") && method === "POST") {
      await delay(options.runDelay ?? 600);
      const message = route.request().postDataJSON().message;
      t1 = { ...t1, status: "RUNNING", run_id: "run-1", run_profile: "audience", events: [{ seq: 1, type: "run.started", message: "开始处理" }], messages: [
        ...t1.messages,
        { id: "u-new", role: "user", text: message, run_id: "run-1", created_at: "2026-09-21T01:01:00Z" },
        ...(options.runWithoutReply ? [] : [{ id: "a-new", role: "assistant", text: "正在整理条件。", run_id: "run-1", created_at: "2026-09-21T01:01:05Z" }]),
      ] };
      return route.fulfill({ json: { code: 200, data: t1 } });
    }
    return route.fulfill({ json: { code: 200, data: t1 } });
  });
  return { finishRun: () => { t1 = { ...t1, status: "COMPLETED" }; } };
}

test("切换会话：点击后立即乐观选中并显示进行中", async ({ page }) => {
  await setup(page, { threadDelay: 700 });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=t1");
  const target = page.locator(".history-item", { hasText: "第二个会话" });
  await expect(target).toBeVisible();
  await target.locator(".history-select").click();
  await expect(target).toHaveClass(/selected/);
  await expect(target).toHaveAttribute("data-pending", "true");
  await expect(page.locator(".topbar-status")).toHaveText("正在打开会话…");
  await expect(page.locator(".conversation")).toHaveAttribute("data-switching", "true");
  await expect(target).not.toHaveAttribute("data-pending", "true", { timeout: 3000 });
  await expect(page.locator(".conversation-heading")).toHaveText("第二个会话");
});

test("发送消息：等待期间出现乐观气泡与发送中提示", async ({ page }) => {
  await setup(page, { runDelay: 700 });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=t1");
  const composer = page.locator(".composer-input");
  await expect(composer).toBeEnabled();
  await composer.fill("近30天转入超50万");
  await composer.press("Enter");
  const ghost = page.locator(".message.is-pending");
  await expect(ghost).toBeVisible({ timeout: 1000 });
  await expect(ghost).toContainText("近30天转入超50万");
  await expect(ghost).toContainText("发送中");
  await expect(page.locator(".composer-hint")).toHaveText("正在发送…");
  await expect(ghost).toHaveCount(0, { timeout: 3000 });
  await expect(page.locator(".thread-viewport")).toContainText("近30天转入超50万");
});

test("空输入不可发送，Shift+Enter 换行，Enter 发送并显示停止", async ({ page }) => {
  await setup(page, { runDelay: 200, runWithoutReply: true });
  await page.goto("/agent-ui/?threadId=t1");
  const input = page.locator(".composer-input");
  const send = page.getByRole("button", { name: "发送需求" });
  await expect(send).toBeDisabled();
  await input.fill("第一行");
  await input.press("Shift+Enter");
  await input.pressSequentially("第二行");
  await expect(input).toHaveValue("第一行\n第二行");
  await input.press("Enter");
  await expect(page.locator('.conversation-turn[data-message-id="u-new"] .message-text')).toHaveText("第一行\n第二行");
  await expect(page.getByRole("button", { name: "停止处理" })).toBeVisible();
});

test("按钮按下时出现可见位移", async ({ page }) => {
  await setup(page);
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=t1");
  const button = page.locator(".new-thread");
  await expect(button).toBeEnabled();
  const box = await button.boundingBox();
  if (!box) throw new Error("新建按钮不可见");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(120);
  const transform = await button.evaluate((el) => getComputedStyle(el).transform);
  expect(transform).not.toBe("none");
  await page.mouse.up();
});

test("统计人数：按钮与状态胶囊显示进行中", async ({ page }) => {
  await setup(page, { countDelay: 700 });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=t1");
  const countButton = page.getByRole("button", { name: "统计人数", exact: true });
  await expect(countButton).toBeVisible();
  await countButton.click();
  await expect(page.locator("button[data-busy='true']")).toContainText("统计中…");
  await expect(page.locator(".plan-status")).toContainText("统计中…");
  await expect(page.locator(".topbar-status")).toHaveText("正在统计人数…");
  await expect(page.locator(".plan-count > strong")).toContainText("1,268", { timeout: 3000 });
});

test("消息悬浮操作：引用保留输入框草稿", async ({ page }) => {
  await setup(page);
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=t1");
  const message = page.locator(".message.user-message").first();
  const actions = message.locator(".message-actions");
  await expect(actions).toHaveCSS("opacity", "0");
  await message.hover();
  await expect(actions).toHaveCSS("opacity", "1");
  const composer = page.locator(".composer-input");
  await composer.fill("分析我刚才的问题");
  await actions.getByRole("button", { name: "引用", exact: true }).click();
  await expect(page.locator(".composer-quote")).toContainText("近30天转入客户");
  await expect(composer).toHaveValue("分析我刚才的问题");
  await page.getByRole("button", { name: "移除消息引用" }).click();
  await expect(page.locator(".composer-quote")).toHaveCount(0);
  await expect(composer).toHaveValue("分析我刚才的问题");
});

test("机器人头像先于处理记录和本轮回复显示", async ({ page }) => {
  const { finishRun } = await setup(page, { runDelay: 200 });
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=t1");
  await page.locator(".composer-input").fill("再分析一次");
  await page.locator(".composer-input").press("Enter");
  await expect(page.locator('.conversation-turn[data-message-id="u-new"]')).toBeVisible({ timeout: 3000 });
  await expect(page.locator(".run-timeline").last()).toBeVisible();
  await expect(page.locator('.conversation-turn[data-message-id="u-new"] .bot-run [aria-label="TagPilot"]')).toBeVisible();
  await expect(page.locator(".message.is-pending")).toHaveCount(0);
  await expect(page.locator('.conversation-turn[data-message-id="a-new"]')).toHaveCount(0);
  await expect(page.locator(".message.is-waiting")).toHaveCount(0);
  finishRun();
  await page.reload();
  await expect(page.locator('.conversation-turn[data-message-id="a-new"]')).toContainText("正在整理条件。");
  await expect(page.locator('.conversation-turn[data-message-id="a-new"] [aria-label="TagPilot"]')).toHaveCount(0);
});

test("处理期间只显示处理记录的机器人头像", async ({ page }) => {
  await setup(page, { runDelay: 200, runWithoutReply: true });
  await page.goto("/agent-ui/?threadId=t1");
  await page.locator(".composer-input").fill("再分析一次");
  await page.locator(".composer-input").press("Enter");
  await expect(page.locator('.conversation-turn[data-message-id="u-new"] .run-timeline')).toBeVisible();
  await expect(page.locator('.conversation-turn[data-message-id="u-new"] .bot-run [aria-label="TagPilot"]')).toHaveCount(1);
  await expect(page.locator(".assistant-message")).toHaveCount(1);
  await expect(page.locator(".message.is-waiting")).toHaveCount(0);
});
