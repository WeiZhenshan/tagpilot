import { test, expect } from "@playwright/test";
import fs from "node:fs";
// 明确的合成数据，只验证交互状态；不代表模型或业务圈选准确率。
const plan = {
  revision: 1,
  hash: "test-hash",
  valid: true,
  build_id: "test-build",
  snapshot_id: "test-snapshot",
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
        allowed_operators: [">", ">=", "between"],
        definition: "近30天异名跨行转入金额合计。此为界面测试数据。",
        time_constraint: "近30天",
        candidates: [{ tag_id: 1, name: "近30天异名跨行转入金额" }],
      },
      {
        clause_id: "b",
        source_span: "排除销户客户",
        tag_id: 2,
        name: "客户状态",
        operator: "not_in",
        values: ["CLOSED"],
        status: "BOUND",
        allowed_operators: ["in", "not_in"],
        code_options: [
          { code: "ACTIVE", label: "正常" },
          { code: "CLOSED", label: "已销户" },
        ],
        candidates: [{ tag_id: 2, name: "客户状态" }],
      },
    ],
  },
};
let t: any;
let deleted = false;
let createdThreads = 0;
test.beforeEach(async ({ page }) => {
  if (process.env.CAPTURE_DIR) fs.mkdirSync(process.env.CAPTURE_DIR, { recursive: true });
  deleted = false;
  createdThreads = 0;
  t = {
    thread_id: "test-thread",
    title: "跨行资金转入客户",
    library_id: 107,
    archived: false,
    status: "COMPLETED",
    revision: 1,
    plan: structuredClone(plan),
    versions: [structuredClone(plan)],
    messages: [
      {
        id: "u",
        role: "user",
        text: "近30天异名跨行转入超过50万元，排除销户客户",
        created_at: "2026-09-21T01:00:00Z",
      },
      {
        id: "a",
        role: "assistant",
        text: "圈选方案已生成，可以核对条件并统计人数。",
        created_at: "2026-09-21T01:00:05Z",
      },
    ],
    events: [
      { seq: 1, type: "intent.ready", message: "已拆解两项圈选条件" },
      { seq: 2, type: "tool.completed", message: "已核对金额及客户状态口径" },
      {
        seq: 3,
        type: "plan.validated",
        plan: structuredClone(plan),
        message: "圈选条件校验通过",
      },
    ],
    capabilities: { count: true, create: true, preview: true },
  };
  await page.route("**/dev-api/**", async (route) => {
    const url = new URL(route.request().url()),
      body = route.request().postDataJSON();
    let data: any;
    if (url.pathname.endsWith("/getInfo"))
      return route.fulfill({
        json: {
          code: 200,
          user: { userId: 2, userName: "demo", nickName: "测试用户" },
        },
      });
    if (url.pathname.endsWith("/library/list"))
      return route.fulfill({
        json: {
          code: 200,
          rows: [
            { libraryId: 107, libraryName: "个人客户经营标签库" },
            { libraryId: 108, libraryName: "公司客户经营标签库" },
          ],
        },
      });
    if (url.pathname.endsWith("/tags/tree")) return route.fulfill({ json: { code: 200, data: [] } });
    if (url.pathname.endsWith("/events")) {
      t.status = "COMPLETED";
      return route.fulfill({
        contentType: "text/event-stream",
        body: `event: state\ndata: ${JSON.stringify(t)}\n\n`,
      });
    }
    if (url.pathname.endsWith("/threads")) {
      if (route.request().method() === "GET") {
        data = deleted || url.searchParams.get("archived") !== String(!!t.archived)
          ? []
          : [
              {
                threadId: t.thread_id,
                title: t.title,
                libraryId: 107,
                archived: t.archived ? "1" : "0",
                pinned: t.pinned ? "1" : "0",
                updateTime: "2026-09-21 09:00:00",
              },
            ];
      } else {
        createdThreads++;
        t = {
          thread_id: `new-thread-${createdThreads}`,
          title: "新的圈选",
          library_id: Number(body.library_id),
          archived: false,
          pinned: false,
          status: "IDLE",
          revision: 0,
          messages: [],
          versions: [],
          events: [],
          capabilities: { count: true, create: true, preview: true },
        };
        data = t;
      }
    } else if (route.request().method() === "DELETE") {
      deleted = true;
      data = null;
    }
    else if (route.request().method() === "PATCH") {
      if (typeof body.title === "string") t.title = body.title;
      if (typeof body.pinned === "boolean") t.pinned = body.pinned;
      if (typeof body.archived === "boolean") {
        t.archived = body.archived;
        if (body.archived) t.pinned = false;
      }
      data = t;
    }
    else if (url.pathname.endsWith("/count")) {
      t.count = {
        value: 1268,
        revision: t.revision,
        executed_at: "2026-09-21T01:05:00Z",
      };
      data = t;
    } else if (
      url.pathname.endsWith("/runs") ||
      url.pathname.endsWith("/resume")
    ) {
      t.plan = body.plan || body.answer?.plan || t.plan || structuredClone(plan);
      t.revision++;
      t.plan.revision = t.revision;
      t.plan.valid = true;
      t.plan.plan_status = "READY";
      t.plan.diagnostics = [];
      if (body.confirmed_clause_ids?.length) {
        t.confirmed_clause_ids = body.confirmed_clause_ids;
        const confirm = (tree: any) => {
          if (tree.children) tree.children.forEach(confirm);
          else if (body.confirmed_clause_ids.includes(tree.clause_id)) {
            tree.status = "BOUND";
            tree.assumption_confirmed = true;
          }
        };
        confirm(t.plan.tree);
      }
      if (t.outcome) t.outcome.gaps = [];
      t.versions.push(structuredClone(t.plan));
      t.status = "RUNNING";
      t.questions = [];
      delete t.count;
      data = t;
    } else if (url.pathname.endsWith("/create-group")) {
      t.execution = { group_id: 99, revision: t.revision };
      data = t.execution;
    } else if (url.pathname.endsWith("/cancel")) {
      t.status = "CANCELLED";
      data = t;
    } else if (url.pathname.endsWith("/preview"))
      data = { displayRows: [{ 客户号: "TEST-001", 客户状态: "正常" }] };
    else data = t;
    return route.fulfill({ json: { code: 200, data } });
  });
});
test("legacy clarification asks metric before its threshold", async ({ page }) => {
  t.status = "WAITING"; t.interrupt_id = "legacy-ask"; t.plan.valid = false;
  t.questions = [
    { requirement_id: "R1", clause_id: "C1", prompt: "高价值客户采用哪个指标？", options: ["最高客户等级 A/B/C", "潜力等级 01至05"], reason: "MULTIPLE_PUBLISHED_DEFINITIONS" },
    { requirement_id: "R1", clause_id: "C1", prompt: "采用哪个档位？", options: ["仅最高档 05极高", "04及05"], reason: "THRESHOLD_MISSING" },
  ];
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=test-thread");
  const ask = page.locator(".ask-card");
  await expect(ask.getByText("高价值客户采用哪个指标？")).toBeVisible();
  await expect(ask.getByText("采用哪个档位？")).toHaveCount(0);
  await expect(ask.getByText("先确认采用的指标，再选择该指标对应的档位或阈值。")).toBeVisible();
  await ask.getByRole("button", { name: "最高客户等级 A/B/C", exact: true }).click();
  if (process.env.CAPTURE_DIR) await page.screenshot({ path: process.env.CAPTURE_DIR + "/clarification-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(ask.getByRole("button", { name: "提交并继续" })).toBeVisible();
  if (process.env.CAPTURE_DIR) await page.screenshot({ path: process.env.CAPTURE_DIR + "/clarification-mobile.png", fullPage: true });
  const posted = page.waitForRequest((r) => r.url().endsWith("/resume"));
  await ask.getByRole("button", { name: "提交并继续" }).click();
  const answer = (await posted).postDataJSON().answer;
  expect(answer).toContain("最高客户等级 A/B/C");
  expect(answer).not.toContain("05极高");
});

test("historical zero-condition degradation remains visible after cancellation", async ({ page }) => {
  t.status = "CANCELLED"; t.plan.valid = false;
  t.events = [{ seq: -1, type: "run.cancelled" }];
  t.run_history = [{ run_id: "old-timeout", events: [{ seq: 1, type: "run.degraded", stats: { degraded: {
    level: "L2", reason: "timeout", kept_clauses: [], unresolved_clause_ids: ["C1"], resumable: true,
    user_message: "处理时间较长，已保留已确认的条件",
  } } }] }];
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=test-thread");
  const history = page.getByRole("region", { name: "第 1 轮处理记录" });
  // section 有标签时由浏览器映射为 region。
  await expect(history.getByRole("button", { name: /部分完成 · 已保留 0 项条件，1 项待处理/ })).toBeVisible();
  await history.locator(".run-heading").click();
  await expect(history.getByText(/尚未形成可用条件/)).toBeVisible();
  if (process.env.CAPTURE_DIR) await page.screenshot({ path: process.env.CAPTURE_DIR + "/history-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(history.getByText(/尚未形成可用条件/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (process.env.CAPTURE_DIR) await page.screenshot({ path: process.env.CAPTURE_DIR + "/history-mobile.png", fullPage: true });
  await page.reload();
  await expect(page.getByRole("button", { name: /第 1 轮处理记录 · 部分完成/ })).toBeVisible();
});
test("condition edits invalidate count, persist through refresh, and creation needs confirmation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=test-thread");
  await expect(
    page.getByRole("button", { name: "统计人数", exact: true })
  ).toBeEnabled();
  await page.getByRole("button", { name: "统计人数", exact: true }).click();
  await expect(page.getByText("1,268")).toBeVisible();
  await page.getByRole("button", { name: "编辑条件：近30天异名跨行转入金额" }).click();
  await page.getByLabel("近30天异名跨行转入金额条件值").fill("600000");
  await expect(
    page.getByRole("button", { name: "保存并核验" })
  ).toBeVisible();
  await page.getByRole("button", { name: "保存并核验" }).click();
  await expect(
    page.getByRole("button", { name: "统计人数", exact: true })
  ).toBeEnabled();
  await expect(page.getByText("1,268")).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "编辑条件：近30天异名跨行转入金额" }).click();
  await expect(page.getByLabel("近30天异名跨行转入金额条件值")).toHaveValue(
    "600000"
  );
  await page.getByRole("button", { name: "完成", exact: true }).click();
  await page.getByRole("button", { name: "统计人数", exact: true }).click();
  await page.getByRole("button", { name: "创建客群", exact: true }).click();
  await expect(page.getByRole("button", { name: "确认创建" })).toBeVisible();
  await page.getByLabel("客群名称").fill("界面测试客群");
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(
    page.getByRole("button", { name: "打开客群" })
  ).toBeVisible();
});
test("clarification and responsive layout remain usable", async ({ page }) => {
  t.status = "WAITING";
  t.interrupt_id = "ask1";
  t.questions = [
    {
      clause_id: "a",
      prompt: "时间范围是近30天还是上个自然月？",
      options: ["近30天", "上个自然月"],
    },
  ];
  t.plan.valid = false;
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=test-thread");
  await expect(page.getByRole("button", { name: "提交并继续" })).toBeDisabled();
  await expect(page.locator(".ask-card").getByRole("button", { name: "停止处理" })).toBeVisible();
  await expect(page.getByRole("button", { name: "归档会话：跨行资金转入客户" })).toBeEnabled();
  if (process.env.CAPTURE_DIR) {
    fs.mkdirSync(process.env.CAPTURE_DIR, { recursive: true });
    await page.screenshot({
      animations: "disabled",
      path: process.env.CAPTURE_DIR + "/desktop-ask.png",
    });
  }
  await page.getByRole("button", { name: "近30天", exact: true }).click();
  await page.getByRole("button", { name: "提交并继续" }).click();
  await expect(
    page.getByRole("button", { name: "统计人数", exact: true })
  ).toBeEnabled();
  if (process.env.CAPTURE_DIR)
    await page.screenshot({
      animations: "disabled",
      path: process.env.CAPTURE_DIR + "/desktop-plan.png",
    });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("tab", { name: "圈选方案", exact: true }).click();
  await expect(
    page.getByRole("tab", { name: "圈选方案", exact: true })
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("近30天异名跨行转入金额 大于 500000元", { exact: true })).toBeVisible();
  await expect(page.getByLabel("近30天异名跨行转入金额条件值")).toHaveCount(0);
  await page.evaluate(() => new Promise(requestAnimationFrame));
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth
    )
  ).toBeTruthy();
  if (process.env.CAPTURE_DIR)
    await page.screenshot({
      animations: "disabled",
      path: process.env.CAPTURE_DIR + "/mobile-plan.png",
    });
});

test("sample dialog traps focus, closes on Escape, and restores focus", async ({
  page,
}) => {
  await page.goto("/agent-ui/?threadId=test-thread");
  await page.getByRole("button", { name: "查看样例客户" }).click();
  await expect(page.getByRole("dialog", { name: "客户样例" })).toBeVisible();
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() => !!document.activeElement?.closest("dialog"))
  ).toBeTruthy();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "查看样例客户" })).toBeFocused();
});

test("mobile errors remain visible and history is accessible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/agent-ui/?threadId=test-thread");
  await page.getByRole("tab", { name: "圈选方案", exact: true }).click();
  await page.route("**/test-thread/count", (r) =>
    r.fulfill({ json: { code: 409, msg: "方案已更新，请重新核验" } })
  );
  await page.getByRole("button", { name: "统计人数", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  if (process.env.CAPTURE_DIR)
    await page.screenshot({
      animations: "disabled",
      path: process.env.CAPTURE_DIR + "/mobile-error.png",
    });
  await page.getByRole("tab", { name: "侧栏", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "圈选会话" })
  ).toBeVisible();
});

test("new draft keeps its identity while changing libraries", async ({ page }) => {
  await page.goto("/agent-ui/?threadId=test-thread");
  await page.getByRole("button", { name: "新建圈选" }).click();
  await expect(page.locator(".conversation-heading")).toHaveText("新的圈选");

  const composer = page.getByPlaceholder("描述客户条件，输入 / 调用技能…");
  await composer.fill("圈选公司客户中的高价值客户");
  const libraryPicker = page.getByRole("button", { name: "当前标签库" });
  await libraryPicker.click();
  await page.getByRole("option", { name: "公司客户经营标签库" }).click();

  await expect(libraryPicker).toContainText("公司客户经营标签库");
  await expect(composer).toHaveValue("圈选公司客户中的高价值客户");
  expect(createdThreads).toBe(0);
  await expect(page).not.toHaveURL(/threadId=/);
  await page.getByRole("button", { name: "发送需求" }).click();
  await expect.poll(() => createdThreads).toBe(1);
  expect(t.library_id).toBe(108);
});

test("library picker sits in the composer and opens above its trigger", async ({
  page,
}) => {
  await page.goto("/agent-ui/");
  const trigger = page
    .locator(".composer-footer")
    .getByRole("button", { name: "当前标签库" });
  await expect(trigger).toBeVisible();
  await trigger.click();
  const listbox = page.getByRole("listbox", { name: "选择标签库" });
  await expect(listbox).toBeVisible();

  const triggerBox = await trigger.boundingBox();
  const listboxBox = await listbox.boundingBox();
  expect(triggerBox).not.toBeNull();
  expect(listboxBox).not.toBeNull();
  expect(listboxBox!.y + listboxBox!.height).toBeLessThanOrEqual(
    triggerBox!.y + 1
  );

  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(trigger).toContainText("公司客户经营标签库");
});

test("return to latest stays fixed while browsing older messages", async ({
  page,
}) => {
  t.messages = Array.from({ length: 30 }, (_, index) => ({
    id: `long-message-${index}`,
    role: index % 2 === 0 ? "user" : "assistant",
    text: `第 ${index + 1} 条用于验证滚动定位的对话消息`,
    created_at: "2026-09-21T01:00:00Z",
  }));
  await page.setViewportSize({ width: 1440, height: 682 });
  await page.goto("/agent-ui/?threadId=test-thread");

  const viewport = page.locator(".thread-viewport");
  const returnButton = page.getByRole("button", { name: "回到最新消息" });
  await expect(page.locator(".run-timeline .sr-only")).toHaveCount(1);
  // 长对话和处理记录只应撑开内部滚动区，不能在整页下方留下空白。
  const expectDocumentToFit = async () => {
    await expect.poll(() => page.evaluate(() =>
      document.documentElement.scrollHeight - innerHeight
    )).toBeLessThanOrEqual(0);
    expect(await viewport.evaluate((element) =>
      element.scrollHeight > element.clientHeight
    )).toBeTruthy();
  };
  await expectDocumentToFit();
  await page.setViewportSize({ width: 596, height: 773 });
  await expectDocumentToFit();
  await expect(returnButton).toBeHidden();
  await viewport.evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(returnButton).toBeVisible();
  await expect(returnButton).toBeEnabled();
  await expectDocumentToFit();

  const settledBox = async () => {
    let previous = await returnButton.boundingBox();
    for (let attempt = 0; attempt < 40; attempt += 1) {
      await page.waitForTimeout(25);
      const current = await returnButton.boundingBox();
      if (
        previous &&
        current &&
        Math.abs(current.y - previous.y) < 0.01 &&
        Math.abs(current.x - previous.x) < 0.01
      )
        return current;
      previous = current;
    }
    return previous;
  };
  const initialBox = await settledBox();
  await viewport.evaluate((element) => {
    element.scrollTop = Math.floor(element.scrollHeight / 3);
    element.dispatchEvent(new Event("scroll"));
  });
  const scrolledBox = await settledBox();
  expect(initialBox).not.toBeNull();
  expect(scrolledBox).not.toBeNull();
  expect(Math.abs(scrolledBox!.y - initialBox!.y)).toBeLessThan(1);

  await returnButton.click();
  await expect
    .poll(() =>
      viewport.evaluate(
        (element) =>
          element.scrollHeight - element.scrollTop - element.clientHeight
      )
    )
    .toBeLessThan(2);
  await expect(returnButton).toBeHidden();
  await expectDocumentToFit();
});

test("history rail supports collapse, inline rename, row actions and account menu", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=test-thread");

  await expect(page.getByRole("button", { name: "重命名" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "上一页" })).toHaveCount(0);
  const row = page.getByRole("button", { name: /跨行资金转入客户/ }).first();
  await row.dblclick();
  const editor = page.getByLabel("编辑会话名称：跨行资金转入客户");
  await editor.fill("重点资金转入客户");
  await editor.press("Enter");
  await expect(page.getByText("重点资金转入客户", { exact: true }).last()).toBeVisible();

  const renamedRow = page.getByRole("button", { name: /重点资金转入客户/ }).first();
  await renamedRow.hover();
  const pin = page.getByRole("button", { name: "置顶：重点资金转入客户" });
  await expect(pin).toHaveAttribute("data-tooltip", "置顶");
  await pin.hover();
  await expect.poll(() =>
    pin.evaluate((node) => getComputedStyle(node, "::after").opacity)
  ).toBe("1");
  await pin.click();
  await expect(
    page.getByRole("button", { name: "取消置顶：重点资金转入客户" })
  ).toBeVisible();
  await expect(renamedRow.locator(".history-pinned")).toBeVisible();
  const archive = page.getByRole("button", { name: "归档会话：重点资金转入客户" });
  await expect(archive).toHaveAttribute("data-tooltip", "归档");
  await archive.click();

  await page.getByRole("button", { name: /测试用户/ }).click();
  await expect(page.getByRole("menuitem", { name: "个人中心" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "退出登录" })).toBeVisible();
  await page.getByRole("menuitem", { name: "查看归档" }).click();
  await expect(page.getByText("已归档", { exact: true })).toBeVisible();
  const archivedRow = page.getByRole("button", { name: /重点资金转入客户/ }).first();
  await archivedRow.hover();
  await expect(page.locator(".history-select small")).toHaveCount(0);
  const restore = page.getByRole("button", { name: "取消归档：重点资金转入客户" });
  const remove = page.getByRole("button", { name: "删除：重点资金转入客户" });
  await expect(restore).toHaveAttribute("data-tooltip", "取消归档");
  await expect(remove).toHaveAttribute("data-tooltip", "删除");
  await remove.hover();
  await expect.poll(() =>
    remove.evaluate((node) => getComputedStyle(node, "::after").opacity)
  ).toBe("1");
  await remove.click();
  const confirmation = page.getByRole("dialog", { name: "永久删除会话？" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toContainText("都无法恢复");
  await confirmation.getByRole("button", { name: "取消" }).click();
  await expect(archivedRow).toBeVisible();
  await archivedRow.hover();
  await page.getByRole("button", { name: "删除：重点资金转入客户" }).click();
  await page.getByRole("button", { name: "永久删除" }).click();
  await expect(page.getByText("没有已归档的圈选")).toBeVisible();

  await page.getByRole("button", { name: "收起历史侧边栏" }).click();
  await expect(page.getByRole("navigation", { name: "圈选会话" })).toBeHidden();
  await page.getByRole("button", { name: "展开历史侧边栏" }).click();
  await expect(page.getByRole("navigation", { name: "圈选会话" })).toBeVisible();
});

test("inline editors and logic selector fit the plan panel", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/?threadId=test-thread");
  const panel = page.getByRole("complementary", { name: "圈选方案" });
  const panelBox = await panel.boundingBox();
  for (const clause of ["近30天异名跨行转入金额", "客户状态"]) {
    await page.getByRole("button", { name: `编辑条件：${clause}` }).click();
    await expect(page.locator(".clause-editor")).toHaveCount(1);
    const label = clause === "客户状态" ? `${clause}条件值` : `${clause}比较方式`;
    const trigger = page.getByRole("button", { name: label, exact: true });
    await trigger.click();
    const listbox = page.getByRole("listbox", { name: label, exact: true });
    const optionsBox = await listbox.boundingBox();
    const triggerBox = await trigger.boundingBox();
    expect(optionsBox!.width).toBeGreaterThanOrEqual(triggerBox!.width - 1);
    expect(optionsBox!.width).toBeLessThan(panelBox!.width);
    await page.keyboard.press("Escape");
  }
  await page.getByRole("button", { name: "条件组合：满足以下全部条件" }).click();
  await page.getByRole("button", { name: "条件组合", exact: true }).click();
  await expect(page.getByRole("option", { name: "满足以下任一条件" })).toBeVisible();
  await page.keyboard.press("Escape");
});

test('计算草案展示缺口且禁止执行',async({page})=>{
  t.outcome={outcome:'CAPABILITY_GAP',gaps:[{requirement_id:'ratio',reason:'NO_CAPABILITY',nearest_tag_ids:[]}]};
  t.plan={...structuredClone(plan),valid:false,plan_status:'CAPABILITY_GAP',tree:{kind:'DERIVED_PREDICATE',clause_id:'ratio',name:'存款占 AUM 至少八成',operator:'>=',values:['0.8'],expression:{kind:'DIV',args:[{kind:'TAG',tag_id:1,name:'当前存款余额'},{kind:'TAG',tag_id:2,name:'当前 AUM'}]}},diagnostics:[{code:'CAPABILITY_UNAVAILABLE',message:'当前发布版本缺少可核验的基金持仓明细能力',user_decision_required:false}]};
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.locator('.clause-copy')).toContainText('(当前存款余额 ÷ 当前 AUM) 至少 0.8');
  await expect(page.getByRole('region',{name:'待处理事项'})).toBeVisible();
  await page.getByRole('button',{name:'先跳过'}).click();
  await expect(page.getByText('当前发布版本缺少可核验的基金持仓明细能力')).toBeVisible();
  await expect(page.getByRole('button',{name:'统计人数',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'创建客群',exact:true})).toHaveCount(0);
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:900});
    if(width===390){const tab=page.getByRole('tab',{name:/方案/});if(await tab.count()){await tab.click();await expect(tab).toHaveAttribute('aria-selected','true');}}
    if(process.env.CAPTURE_DIR)await page.screenshot({path:`${process.env.CAPTURE_DIR}/v3-gap-${width}.png`,fullPage:true});
  }
});

test('预算降级保留部分方案，补全使用新消息且不可执行', async ({page}) => {
  t.plan.valid=false;t.plan.plan_status='DRAFT';
  t.plan.tree.children[1].status='GAP';t.plan.tree.children[1].gap_reason='BUDGET_EXHAUSTED';
  t.outcome={outcome:'PARTIAL',gaps:[],stats:{degraded:{level:'L2',reason:'timeout',kept_clauses:['a'],unresolved_clause_ids:['b'],resumable:true,resume_mode:'lean',attempt:1,user_message:'处理时间较长，已保留已确认的条件',ops_alert:false}}};
  await page.setViewportSize({width:1440,height:960});
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.getByText('已保留 1/2 项条件')).toBeVisible();
  await expect(page.locator('.run-error')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'统计人数',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'创建客群',exact:true})).toHaveCount(0);
  await expect(page.getByText('部分完成',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'手工编辑方案',exact:true}).click();
  await expect(page.locator('#agent-plan-editor')).toBeFocused();
  if(process.env.CAPTURE_DIR)await page.screenshot({path:`${process.env.CAPTURE_DIR}/degrade-desktop.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('tab',{name:/对话/}).click();
  await expect(page.getByText('已保留 1/2 项条件')).toBeVisible();
  if(process.env.CAPTURE_DIR)await page.screenshot({path:`${process.env.CAPTURE_DIR}/degrade-mobile.png`,fullPage:true});
  const sent=page.waitForRequest(request=>request.url().endsWith('/runs')&&request.method()==='POST');
  await page.getByRole('button',{name:'补全剩余条件',exact:true}).click();
  expect((await sent).postDataJSON().message).toBe('请继续补全尚未确定的条件');
});

test('候选建议能选标签，超过续跑次数只提供编辑入口', async ({page})=>{
  t.plan.valid=false;t.plan.plan_status='CAPABILITY_GAP';
  t.plan.tree.children[0].gap_reason='BUDGET_EXHAUSTED';
  t.outcome={outcome:'PARTIAL',gaps:[{requirement_id:'a',reason:'NO_PUBLISHED_TAG',nearest_tag_ids:[1]}],stats:{degraded:{level:'L3',reason:'max_turns',kept_clauses:[],unresolved_clause_ids:['a','b'],resumable:false,resume_mode:'lean',attempt:3,ops_alert:false}}};
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.getByRole('button',{name:'补全剩余条件',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'手工编辑方案',exact:true})).toBeVisible();
  await expect(page.getByText('已找到可能相关的标签，请在方案中选择并核验。')).toBeVisible();
  await expect(page.getByText('这项条件暂未确定，候选标签尚待核验')).toBeVisible();
  await page.getByRole('button',{name:'编辑条件：近30天异名跨行转入金额',exact:true}).click();
  await page.getByRole('button',{name:'采用标签：近30天异名跨行转入金额',exact:true}).click();
  await expect(page.getByRole('button',{name:'保存并核验',exact:true})).toBeVisible();
});

test('排队超时显示对应错误及稍后重试',async({page})=>{
  t.status='FAILED';t.plan.valid=false;t.plan.plan_status='RETRYABLE_FAILURE';
  t.outcome={outcome:'PARTIAL',gaps:[],stats:{degraded:{level:'L4',reason:'queue_timeout',kept_clauses:[],unresolved_clause_ids:['a','b'],resumable:true,resume_mode:'retry',attempt:0,ops_alert:false}}};
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.locator('.run-error')).toContainText('当前使用人数较多，排队已超时');
  await expect(page.getByRole('button',{name:'稍后重试',exact:true})).toBeVisible();
  await expect(page.locator('.run-degraded')).toHaveCount(0);
});

test('摘要、口径、菜单和版本只读状态按需展示', async ({page})=>{
  t.revision=2;
  t.plan.revision=2;
  t.plan.tree.children[0].values=['600000'];
  t.plan.tree.children.pop();
  t.versions.push(structuredClone(t.plan));
  t.count={value:0,revision:2,executed_at:'2026-09-29T01:30:00Z',data_as_of:'2026-09-28'};
  await page.setViewportSize({width:1440,height:960});
  await page.goto('/agent-ui/?threadId=test-thread');
  const panel=page.getByRole('complementary',{name:'圈选方案'});
  await expect(panel.locator('.clause-copy')).toContainText('近30天异名跨行转入金额 大于 600000元');
  await expect(panel.locator('.clause-change')).toHaveText('改');
  await expect(panel.locator('.removed-clause del')).toContainText('客户状态 不属于 已销户');
  await expect(panel.locator('.clause-editor')).toHaveCount(0);
  await expect(panel.getByText('已匹配',{exact:true})).toHaveCount(0);
  await expect(panel.locator('.plan-count > strong')).toHaveText('0 人');
  await expect(panel.getByRole('button',{name:'创建客群',exact:true})).toBeEnabled();
  await expect(panel.getByText('test-snapshot')).toHaveCount(0);
  await panel.getByRole('button',{name:'近30天异名跨行转入金额口径说明'}).click();
  await expect(panel.getByRole('note')).toContainText('近30天异名跨行转入金额合计');
  if(process.env.CAPTURE_DIR)await page.screenshot({path:`${process.env.CAPTURE_DIR}/summary-count-desktop.png`});
  await panel.getByRole('button',{name:'方案更多操作'}).click();
  await page.getByRole('button',{name:'技术详情',exact:true}).click();
  const technical=page.getByRole('dialog',{name:'技术详情'});
  await expect(technical).toContainText('test-snapshot');
  await page.keyboard.press('Escape');
  await expect(panel.getByRole('button',{name:'方案更多操作'})).toBeFocused();
  await panel.getByRole('button',{name:'方案更多操作'}).click();
  await page.getByRole('button',{name:'原始需求',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'原始需求'})).toContainText(t.messages[0].text);
  await page.keyboard.press('Escape');
  await panel.getByRole('button',{name:'方案更多操作'}).click();
  await page.getByRole('button',{name:'版本历史',exact:true}).click();
  await page.getByRole('dialog',{name:'版本历史'}).getByRole('button',{name:/^v1/}).click();
  await expect(panel).toContainText('你正在查看 v1');
  await expect(panel.getByRole('button',{name:'编辑条件：客户状态'})).toBeDisabled();
  await expect(panel.getByRole('button',{name:'以此版本继续',exact:true})).toBeEnabled();
  await expect(panel.locator('.plan-count')).toHaveCount(0);
  await panel.getByRole('button',{name:'返回当前',exact:true}).click();
  await expect(panel.locator('.plan-count > strong')).toHaveText('0 人');
  await panel.getByRole('button',{name:'编辑条件：近30天异名跨行转入金额'}).click();
  await page.getByLabel('近30天异名跨行转入金额条件值').fill('700000');
  await expect(panel.locator('.plan-count > strong')).toHaveText('—');
  await panel.getByRole('button',{name:'方案更多操作'}).click();
  await page.getByRole('button',{name:'版本历史',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'版本历史'}).getByRole('button',{name:/^v1/})).toBeDisabled();
  await page.keyboard.press('Escape');
  await panel.getByRole('button',{name:'放弃修改',exact:true}).click();
  await expect(panel.locator('.plan-count > strong')).toHaveText('0 人');
});

test('待处理逐项确认，跳过不解除阻断，改写预填且不自动发送',async({page})=>{
  t.plan.valid=false;
  t.plan.tree.children[0].status='GAP';
  t.plan.tree.children[0].requirement_ids=['r'];
  t.plan.tree.children[1].status='ASSUMED';
  t.plan.tree.children[1].assumption={status:'PENDING',question:'采用当前客户状态口径？'};
  t.outcome={outcome:'PARTIAL',gaps:[{requirement_id:'r',reason:'CALIBER_UNAVAILABLE',nearest_tag_ids:[]}]};
  await page.setViewportSize({width:390,height:844});
  await page.goto('/agent-ui/?threadId=test-thread');
  await page.getByRole('tab',{name:'圈选方案',exact:true}).click();
  const card=page.getByRole('region',{name:'待处理事项'});
  await expect(card).toContainText('第 1/2 项');
  await expect(card.getByText('采用当前客户状态口径？')).toHaveCount(0);
  await page.getByRole('button',{name:'先跳过'}).click();
  await expect(card).toContainText('采用当前客户状态口径？');
  await expect(page.getByRole('button',{name:'创建客群',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'先跳过'}).click();
  const requests:string[]=[];
  page.on('request',r=>{if(r.method()==='POST')requests.push(r.url());});
  await page.getByRole('button',{name:'换个说法',exact:true}).click();
  const composer=page.getByPlaceholder('描述客户条件，输入 / 调用技能…');
  await expect(composer).toBeFocused();
  await expect(composer).toHaveValue(/我可接受的范围是/);
  await expect(page.getByRole('tab',{name:'对话',exact:true})).toHaveAttribute('aria-selected','true');
  expect(requests).toEqual([]);
});

test('多项定义分别确认，只提交已明确确认的条件',async({page})=>{
  t.plan.valid=false;
  t.confirmed_clause_ids=['a','b']; // 旧版本确认记录不能跳过本版仍为 ASSUMED 的定义。
  t.plan.tree.children.forEach((c:any)=>{c.status='ASSUMED';c.assumption={status:'PENDING',question:`请确认${c.name}口径`};});
  await page.goto('/agent-ui/?threadId=test-thread');
  const card=page.getByRole('region',{name:'待处理事项'});
  await expect(card).toContainText('第 1/2 项');
  await card.getByRole('button',{name:'确认',exact:true}).click();
  await expect(card).toContainText('请确认客户状态口径');
  const sent=page.waitForRequest(r=>r.url().endsWith('/runs')&&r.method()==='POST');
  await card.getByRole('button',{name:'确认',exact:true}).click();
  expect((await sent).postDataJSON().confirmed_clause_ids).toEqual(['a','b']);
  await expect(page.getByRole('button',{name:'统计人数',exact:true})).toBeEnabled();
});

test('嵌套条件、单项编辑、删除和放弃保持逻辑',async({page})=>{
  const second=t.plan.tree.children.pop();
  t.plan.tree.children.push({logic:'OR',children:[second,{...second,clause_id:'c',name:'备用客户状态',operator:'in',values:['ACTIVE']}]});
  t.versions=[structuredClone(t.plan)];
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.getByRole('button',{name:'条件组合：满足以下任一条件'})).toBeVisible();
  await page.getByRole('button',{name:'编辑条件：客户状态',exact:true}).click();
  await page.getByRole('button',{name:'删除此条件',exact:true}).click();
  await expect(page.locator('.clause-copy')).toHaveCount(2);
  await expect(page.getByRole('button',{name:'保存并核验',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'放弃修改',exact:true}).click();
  await expect(page.locator('.clause-copy')).toHaveCount(3);
  await page.getByRole('button',{name:'编辑条件：近30天异名跨行转入金额'}).click();
  await page.getByRole('button',{name:'编辑条件：备用客户状态'}).click();
  await expect(page.locator('.clause-editor')).toHaveCount(1);
  await expect(page.getByLabel('近30天异名跨行转入金额条件值')).toHaveCount(0);
});

test('过期人数不显示，权限与处理状态约束主动作',async({page})=>{
  t.count={value:999,revision:0,executed_at:'bad-date'};
  t.capabilities.count=false;
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.locator('.plan-count > strong')).toHaveText('—');
  await expect(page.getByRole('button',{name:'统计人数',exact:true})).toBeDisabled();
  await expect(page.getByText('当前账号暂无统计权限。')).toBeVisible();
});

test('空态与处理中的方案只呈现当前动作',async({page})=>{
  t.plan=undefined;t.versions=[];t.messages=[];t.revision=0;t.status='IDLE';
  await page.goto('/agent-ui/?threadId=test-thread');
  const panel=page.getByRole('complementary',{name:'圈选方案'});
  await expect(panel).toContainText('先描述你想寻找的客户');
  await expect(panel.locator('.plan-actions')).toHaveCount(0);
  t.plan=structuredClone(plan);t.live_plan=structuredClone(plan);t.revision=1;t.status='RUNNING';
  await page.reload();
  await expect(panel).toContainText('正在整理条件…');
  await expect(panel.locator('.plan-actions')).toHaveCount(0);
  await expect(panel.getByRole('button',{name:'编辑条件：客户状态'})).toBeDisabled();
  const sent=page.waitForRequest(r=>r.url().endsWith('/cancel')&&r.method()==='POST');
  await panel.getByRole('button',{name:'停止',exact:true}).click();
  await sent;
});

test('复制方案文字保留中文码值及嵌套关系',async({page,context})=>{
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  await page.goto('/agent-ui/?threadId=test-thread');
  await page.getByRole('button',{name:'方案更多操作'}).click();
  await page.getByRole('button',{name:'复制方案文字',exact:true}).click();
  await expect(page.getByText('已复制方案文字',{exact:true})).toBeVisible();
  const text=await page.evaluate(()=>navigator.clipboard.readText());
  expect(text).toContain('满足以下全部条件');expect(text).toContain('客户状态 不属于 已销户');expect(text).not.toContain('CLOSED');
});

test('定义确认提交失败后保留当前待办并可重试',async({page})=>{
  t.plan.valid=false;
  t.plan.tree.children.forEach((c:any)=>{c.status='ASSUMED';c.assumption={status:'PENDING',question:`请确认${c.name}口径`};});
  let fail=true;
  await page.route('**/runs',async route=>{
    if(fail){fail=false;await route.fulfill({json:{code:500,msg:'暂时无法保存，请重试'}});}
    else await route.fallback();
  });
  await page.goto('/agent-ui/?threadId=test-thread');
  const card=page.getByRole('region',{name:'待处理事项'});
  await card.getByRole('button',{name:'确认',exact:true}).click();
  await card.getByRole('button',{name:'确认',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('暂时无法保存');
  await expect(card).toContainText('请确认客户状态口径');
  const sent=page.waitForRequest(r=>r.url().endsWith('/runs')&&r.method()==='POST');
  await card.getByRole('button',{name:'确认',exact:true}).click();
  expect((await sent).postDataJSON().confirmed_clause_ids).toEqual(['a','b']);
  await expect(page.getByRole('button',{name:'统计人数',exact:true})).toBeEnabled();
});

test("streaming timeline paces updates, replays history, and highlights changed conditions", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  const now = Date.now() / 1000;
  t.status = "RUNNING"; t.run_id = "live-run"; t.events = [];
  delete t.plan; t.messages = t.messages.slice(0, 1);
  t.run_history = [{ run_id: "old-run", events: [{ seq: -1, type: "run.cancelled" }, { seq: -1, type: "run.cancelled" }] }];
  await page.route("**/dev-api/**/events", (route) => route.fulfill({ contentType: "text/event-stream", body: `event: state\ndata: ${JSON.stringify(t)}\n\n` }));
  await page.goto("/agent-ui/?threadId=test-thread");
  const current = page.getByRole("region", { name: "处理记录", exact: true });
  await expect(current.locator(".run-content")).toBeVisible();
  await expect(page.getByRole("region", { name: "第 1 轮处理记录" }).locator(".run-content")).toHaveCount(0);
  t.events = [{ seq: 1, type: "narration", text: "先核对转入金额与客户状态的口径", occurred_at: now },
    { seq: 2, type: "tool.started", tool: "find_tags", call_id: "live-1", targets: ["近30天转入"], queries: [{ text: "近30天转入", requirement_id: "R1" }], requirement_ids: ["R1"], occurred_at: now + .2 }];
  await expect(current.locator(".run-todos")).toContainText("近30天转入");
  await expect(current.locator(".run-entries")).toContainText("查找标签「近30天转入」");
  const livePlan: any = structuredClone(plan);
  livePlan.intent_plan = { requirements: [{ requirement_id: "R1", business_meaning: "转入超过50万元" }, { requirement_id: "R2", business_meaning: "排除已销户客户" }] };
  livePlan.tree.children[0].requirement_ids = ["R1"]; livePlan.tree.children[1].requirement_ids = ["R2"];
  t.events.push({ seq: 3, type: "tool.completed", tool: "find_tags", call_id: "live-1", ok: true, summary: "找到 5 个相关标签", items: [{ name: "近30天异名跨行转入金额" }], duration_ms: 400, occurred_at: now + 1 },
    { seq: 4, type: "intent.ready", plan: livePlan, occurred_at: now + 1 },
    { seq: 5, type: "plan.observed", plan: livePlan, occurred_at: now + 1.2 },
    { seq: 6, type: "tool.started", tool: "get_tag_details", call_id: "live-2", targets: ["客户状态"], requirement_ids: ["R2"], occurred_at: now + 1.4 });
  t.live_plan = livePlan;
  await expect(current.locator(".run-entries")).toContainText("核对「客户状态」的口径");
  await expect(current.getByRole("button", { name: /查找标签「近30天转入」/ })).toHaveAttribute("aria-expanded", "false");
  await expect(current.getByRole("button", { name: /核对「客户状态」/ })).toHaveAttribute("aria-expanded", "true");
  if (process.env.CAPTURE_DIR) await page.screenshot({ animations: "disabled", path: process.env.CAPTURE_DIR + "/timeline-running-desktop.png" });
  await page.reload();
  await current.getByRole("button", { name: /已说明：先核对/ }).click();
  await expect(current.locator(".run-narration-text")).toHaveText("先核对转入金额与客户状态的口径");
  await expect(current.locator(".run-caret")).toHaveCount(0);
  t.events.push({ seq: 7, type: "tool.completed", tool: "get_tag_details", call_id: "live-2", ok: true, summary: "已核对客户状态取值", occurred_at: now + 2 },
    { seq: 8, type: "plan.validated", plan: livePlan, occurred_at: now + 3 });
  t.plan = livePlan; t.status = "COMPLETED";
  await expect(current.locator(".run-content")).toHaveCount(0);
  await current.locator(".run-heading").click();
  await current.getByRole("button", { name: "方案变更 · 2 项" }).click();
  await expect(page.locator('.clause-row[data-highlighted="true"]')).toHaveCount(2);
  await page.getByRole("region", { name: "第 1 轮处理记录" }).locator(".run-heading").click();
  await expect(page.getByRole("region", { name: "第 1 轮处理记录" }).locator(".run-entry-status")).toHaveCount(2);
});

test("waiting questions stay inside the timeline and reduced motion preserves replay", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" }); await page.setViewportSize({ width: 390, height: 844 });
  t.status = "WAITING"; t.run_id = "waiting-run"; t.interrupt_id = "choice";
  t.questions = [{ clause_id: "a", prompt: "转入统计口径采用哪个时间范围？", options: ["近30天", "上个自然月"] }]; t.plan.valid = false;
  await page.goto("/agent-ui/?threadId=test-thread");
  const current = page.getByRole("region", { name: "处理记录", exact: true });
  await expect(current.locator(".ask-card")).toBeVisible();
  await expect(current.locator('.run-todos [data-status="blocked"]')).not.toHaveCount(0);
  await expect(current.locator(".run-caret")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  if (process.env.CAPTURE_DIR) await page.screenshot({ animations: "disabled", path: process.env.CAPTURE_DIR + "/timeline-waiting-mobile.png" });
  await current.getByRole("button", { name: "近30天", exact: true }).click();
  await expect(current.getByRole("button", { name: "提交并继续" })).toBeEnabled();
});

test("cancelled and failed operations stop spinning and keep their replay", async ({ page }) => {
  t.status = "CANCELLED"; t.events = [{ seq: 1, type: "tool.started", tool: "find_tags" }, { seq: -1, type: "run.cancelled" }];
  await page.goto("/agent-ui/?threadId=test-thread");
  const current = page.getByRole("region", { name: "处理记录", exact: true });
  await expect(current.locator(".run-content")).toHaveCount(0); await current.locator(".run-heading").click();
  await expect(current.locator(".marker-active")).toHaveCount(0);
  await expect(current.locator(".run-entries")).toContainText("本次操作未完成");
  t.status = "FAILED"; t.error = "检索服务暂不可用"; t.events.push({ seq: 3, type: "run.failed" });
  await page.reload(); await expect(current.locator(".run-heading")).toContainText("已保存处理进度");
  await current.locator(".run-heading").click(); await expect(current.locator(".marker-active")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "从保存位置继续" })).toBeVisible();
});
