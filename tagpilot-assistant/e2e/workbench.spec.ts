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
  await page.getByLabel("近30天异名跨行转入金额条件值").fill("600000");
  await expect(
    page.getByRole("button", { name: "保存并核验修改" })
  ).toBeVisible();
  await page.getByRole("button", { name: "保存并核验修改" }).click();
  await expect(
    page.getByRole("button", { name: "统计人数", exact: true })
  ).toBeEnabled();
  await expect(page.getByText("1,268")).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel("近30天异名跨行转入金额条件值")).toHaveValue(
    "600000"
  );
  await page.getByRole("button", { name: "创建客群", exact: true }).click();
  await expect(page.getByRole("button", { name: "确认创建" })).toBeVisible();
  await page.getByLabel("客群名称").fill("界面测试客群");
  await page.getByRole("button", { name: "确认创建" }).click();
  await expect(
    page.getByRole("button", { name: "打开已创建客群" })
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
  await expect(page.getByLabel("近30天异名跨行转入金额条件值")).toBeVisible();
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
  await page.getByRole("button", { name: "查看样例" }).click();
  await expect(page.getByRole("dialog", { name: "客户样例" })).toBeVisible();
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(() => !!document.activeElement?.closest("dialog"))
  ).toBeTruthy();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "查看样例" })).toBeFocused();
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
  await page.getByRole("tab", { name: "历史", exact: true }).click();
  await expect(
    page.getByRole("navigation", { name: "圈选会话" })
  ).toBeVisible();
});

test("new draft keeps its identity while changing libraries", async ({ page }) => {
  await page.goto("/agent-ui/?threadId=test-thread");
  await page.getByRole("button", { name: "新建圈选" }).click();
  await expect(page.locator(".conversation-heading")).toHaveText("新的圈选");

  const composer = page.getByPlaceholder("描述客户条件，或继续修改当前方案…");
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

test("library picker opens below its trigger", async ({ page }) => {
  await page.goto("/agent-ui/");
  const trigger = page.getByRole("button", { name: "当前标签库" });
  await trigger.click();
  const listbox = page.getByRole("listbox", { name: "选择标签库" });
  await expect(listbox).toBeVisible();

  const triggerBox = await trigger.boundingBox();
  const listboxBox = await listbox.boundingBox();
  expect(triggerBox).not.toBeNull();
  expect(listboxBox).not.toBeNull();
  expect(listboxBox!.y).toBeGreaterThanOrEqual(triggerBox!.y + triggerBox!.height);

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
  await page.setViewportSize({ width: 596, height: 773 });
  await page.goto("/agent-ui/?threadId=test-thread");

  const viewport = page.locator(".thread-viewport");
  const returnButton = page.getByRole("button", { name: "回到最新消息" });
  await expect(returnButton).toBeHidden();
  await viewport.evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(returnButton).toBeVisible();
  await expect(returnButton).toBeEnabled();

  const initialBox = await returnButton.boundingBox();
  await viewport.evaluate((element) => {
    element.scrollTop = Math.floor(element.scrollHeight / 3);
    element.dispatchEvent(new Event("scroll"));
  });
  const scrolledBox = await returnButton.boundingBox();
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

test('计算草案展示缺口且禁止执行',async({page})=>{
  t.plan={...structuredClone(plan),valid:false,plan_status:'CAPABILITY_GAP',tree:{kind:'DERIVED_PREDICATE',clause_id:'ratio',name:'存款占 AUM 至少八成',operator:'>=',values:['0.8'],expression:{kind:'DIV',args:[{kind:'TAG',tag_id:1,name:'当前存款余额'},{kind:'TAG',tag_id:2,name:'当前 AUM'}]}},diagnostics:[{code:'CAPABILITY_UNAVAILABLE',message:'当前发布版本缺少可核验的基金持仓明细能力',user_decision_required:false}]};
  await page.goto('/agent-ui/?threadId=test-thread');
  await expect(page.getByText('存款占 AUM 至少八成',{exact:true})).toBeVisible();
  await expect(page.getByText('当前发布版本缺少可核验的基金持仓明细能力')).toBeVisible();
  await expect(page.getByRole('button',{name:'统计人数',exact:true})).toBeDisabled();
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:900});
    if(width===390){const tab=page.getByRole('tab',{name:/方案/});if(await tab.count()){await tab.click();await expect(tab).toHaveAttribute('aria-selected','true');}}
    if(process.env.CAPTURE_DIR)await page.screenshot({path:`${process.env.CAPTURE_DIR}/v3-gap-${width}.png`,fullPage:true});
  }
});
