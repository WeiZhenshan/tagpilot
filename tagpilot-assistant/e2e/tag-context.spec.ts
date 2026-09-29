import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";

// 合成数据：验证 UI 与协议，无真实 Agent、人数查询或客群写入。
const names = ["活期存款余额", "客户等级", "是否持有信用卡", "近30天借记卡消费金额", "理财风险等级", "客户年龄", "开户日期", "职业分类"];
const tree = [{ id: "lib-107", label: "个人客户经营标签库", children: [{ id: "dir-1", label: "客户经营", children: names.map((label, i) => ({ id: `tag-${i + 1}`, tagId: i + 1, label, tagType: i === 2 ? "布尔型" : i === 1 ? "选项型" : "数值型", dirPath: "客户经营" })) }] }];
const savedPlan = { revision: 1, valid: true, hash: "saved", schema_version: 3, plan_status: "READY", tree: { kind: "TAG_PREDICATE", clause_id: "a", name: names[0], source_span: "活期存款余额至少50万元", tag_id: 1, operator: ">=", values: ["50"], value_unit: "CNY", value_scale: "10000", status: "BOUND" } };
let t: any;
let failNext: boolean;
let requests: any[];
test.beforeEach(async ({ page }) => {
  failNext = false; requests = [];
  t = { thread_id: "tag-thread", library_id: 107, title: "新的圈选", status: "IDLE", revision: 0, archived: false, messages: [], events: [], versions: [], capabilities: { count: true, create: false, update: true, preview: true } };
  await page.route("**/dev-api/**", async (route) => {
    const url = new URL(route.request().url()); const body = route.request().postDataJSON(); let data: any;
    if (url.pathname.endsWith("/getInfo")) return route.fulfill({ json: { code: 200, user: { userId: 2, nickName: "测试用户" } } });
    if (url.pathname.endsWith("/library/list")) return route.fulfill({ json: { code: 200, rows: [{ libraryId: 107, libraryName: "个人客户经营标签库" }, { libraryId: 108, libraryName: "公司客户经营标签库" }] } });
    if (url.pathname.endsWith("/tags/tree")) return route.fulfill({ json: { code: 200, data: url.searchParams.get("libraryId") === "107" ? tree : [] } });
    if (url.pathname.endsWith("/from-group")) {
      t = { ...t, title: "编辑：测试客群", plan: { ...structuredClone(savedPlan), valid: false }, revision: 1, versions: [structuredClone(savedPlan)], source_group_id: 90, source_group_name: "测试客群", source_requires_validation: true, source_thread_reused: false };
      data = t;
    } else if (url.pathname.endsWith("/threads")) data = route.request().method() === "GET" ? [] : t;
    else if (url.pathname.endsWith("/runs")) {
      requests.push(body);
      if (failNext) { failNext = false; return route.fulfill({ json: { code: 409, msg: "发布版本已更新，请重新选择标签" } }); }
      t.revision++;
      if (body.plan) { t.plan = { ...body.plan, valid: true, diagnostics: [], revision: t.revision }; t.source_requires_validation = false; t.status = "COMPLETED"; }
      else {
        t.messages.push({ id: `u${requests.length}`, role: "user", text: body.message, context_tags: body.context_tag_ids.map((id: number) => ({ id, name: names[id - 1] })), created_at: "2026-09-29T00:00:00Z" });
        t.status = "WAITING"; t.interrupt_id = "ask";
        t.questions = [{ requirement_id: "selected", prompt: "这些条件需要同时满足还是满足其一？", options: ["同时满足", "满足其一"] }];
      }
      data = t;
    } else if (url.pathname.endsWith("/cancel")) { t.status = "CANCELLED"; t.questions = []; data = t; }
    else if (url.pathname.endsWith("/count")) { t.count = { value: 1268, revision: t.revision, executed_at: "2026-09-29T00:00:00Z" }; data = t; }
    else if (url.pathname.endsWith("/create-group")) { requests.push(body); data = { group_id: 90, updated: true }; }
    else data = t;
    return route.fulfill({ json: { code: 200, data } });
  });
});
async function showTags(page: Page) {
  await page.getByRole("tab", { name: "标签", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true })).toBeVisible();
}
async function capture(page: Page, name: string) {
  if (!process.env.TAG_CAPTURE_DIR) return;
  fs.mkdirSync(process.env.TAG_CAPTURE_DIR, { recursive: true });
  await page.screenshot({ path: `${process.env.TAG_CAPTURE_DIR}/${name}.png`, fullPage: true, animations: "disabled" });
}
test("目录批量上限、三态、多端浏览与补充说明", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/agent-ui/"); await showTags(page);
  await page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true }).click();
  await expect(page.getByText("已选 5 / 5 项")).toBeVisible();
  await expect(page.getByText(/目录中其余标签未选入/)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true })).toHaveJSProperty("indeterminate", true);
  await page.getByRole("button", { name: "展开目录：客户经营" }).click();
  await expect(page.getByRole("checkbox", { name: `选择标签：${names[5]}`, exact: true })).not.toBeChecked();
  await capture(page, "desktop");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("tab", { name: "会话 / 标签", exact: true }).click();
  await expect(page.getByRole("button", { name: "确认并让智能体梳理" })).toBeVisible();
  await capture(page, "mobile");
  await page.getByRole("button", { name: "确认并让智能体梳理" }).click();
  const dialog = page.getByRole("dialog", { name: "让智能体梳理所选标签" });
  await expect(dialog.getByRole("textbox")).toBeFocused();
  await dialog.getByRole("textbox").fill("具体阈值请逐项询问");
  await capture(page, "supplement-mobile");
  await dialog.getByRole("button", { name: "确认并梳理" }).click();
  await expect(dialog).not.toBeVisible();
  expect(requests[0].context_tag_ids).toEqual([1, 2, 3, 4, 5]);
  expect(requests[0].message).toContain("补充说明：具体阈值请逐项询问"); expect(requests[0].context_only).toBe(false);
  await expect(page.locator(".ask-card")).toBeVisible();
  await expect(page.locator(".user-message .tag-chip")).toHaveCount(5);
});
test("仅选标签发起澄清、归档及WAITING可浏览但不能发起新轮次", async ({ page }) => {
  await page.goto("/agent-ui/"); await showTags(page);
  await page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true }).click();
  await page.getByRole("button", { name: "确认并让智能体梳理" }).click();
  await page.getByRole("button", { name: "确认并梳理", exact: true }).click();
  await expect(page.locator(".ask-card")).toBeVisible(); expect(requests[0].context_only).toBe(true);
  await page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true }).click();
  await expect(page.getByRole("button", { name: "确认并让智能体梳理" })).toBeDisabled();
  await expect(page.getByText("请先回答当前待补充问题")).toBeVisible();
  await page.locator(".ask-card").getByRole("button", { name: "停止处理" }).click();
  await expect(page.getByRole("button", { name: "确认并让智能体梳理" })).toBeEnabled();
  t.archived = true;
  await page.reload(); await showTags(page);
  await page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true }).click();
  await expect(page.getByRole("button", { name: "确认并让智能体梳理" })).toBeDisabled();
  await expect(page.getByText("会话已归档，恢复后可发送")).toBeVisible();
});
test("加入输入框保留草稿、失败保留chip、成功记录历史", async ({ page }) => {
  await page.goto("/agent-ui/");
  await page.locator(".composer-input").fill("帮我确认这些条件的阈值");
  await showTags(page); await page.getByRole("button", { name: "展开目录：客户经营" }).click();
  await page.getByRole("checkbox", { name: `选择标签：${names[0]}`, exact: true }).check();
  await page.getByRole("button", { name: "加入输入框" }).click();
  await expect(page.locator(".composer-input")).toHaveValue("帮我确认这些条件的阈值");
  await expect(page.locator(".composer-tags .tag-chip")).toHaveCount(1);
  failNext = true;
  await page.getByRole("button", { name: "发送需求" }).click();
  await expect(page.getByRole("alert")).toContainText("发布版本已更新");
  await expect(page.locator(".composer-tags .tag-chip")).toHaveCount(1);
  await expect(page.locator(".composer-input")).toHaveValue("帮我确认这些条件的阈值");
  await page.getByRole("button", { name: "发送需求" }).click();
  await expect(page.locator(".composer-tags")).toHaveCount(0);
  await expect(page.locator(".user-message .tag-chip")).toHaveCount(1);
  await page.reload(); await expect(page.locator(".user-message .tag-chip")).toHaveCount(1);
});
test("空白草稿加标签使用默认梳理话术", async ({ page }) => {
  await page.goto("/agent-ui/");
  await page.locator(".composer-input").fill("   ");
  await showTags(page); await page.getByRole("button", { name: "展开目录：客户经营" }).click();
  await page.getByRole("checkbox", { name: `选择标签：${names[0]}`, exact: true }).check();
  await page.getByRole("button", { name: "加入输入框" }).click();
  await expect(page.locator(".composer-input")).toHaveValue("   ");
  await page.getByRole("button", { name: "发送需求" }).click();
  await expect(page.locator(".ask-card")).toBeVisible();
  expect(requests[0].message.trim()).not.toBe("");
  expect(requests[0].message).toContain(names[0]);
  expect(requests[0].context_only).toBe(true);
  expect(requests[0].context_tag_ids).toEqual([1]);
  await expect(page.locator(".composer-tags")).toHaveCount(0);
});
test("客群回跳、已用标签、核验后更新原客群而不复制", async ({ page }) => {
  await page.goto("/agent-ui/?groupId=90&libraryId=108&from=/objectgroup/list");
  await expect(page.getByRole("tab", { name: "标签", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("button", { name: "当前标签库" })).toContainText("个人客户经营标签库");
  await page.getByRole("button", { name: "展开目录：客户经营" }).click();
  await expect(page.getByRole("checkbox", { name: `选择标签：${names[0]}`, exact: true })).toBeDisabled();
  await expect(page.getByText("已在方案中", { exact: true })).toBeVisible();
  expect(requests).toHaveLength(0);
  await page.getByRole("button", { name: "按最新发布版本核验" }).click();
  await expect(page.getByRole("button", { name: "统计人数", exact: true })).toBeEnabled();
  expect(requests[0].plan.tree.tag_id).toBe(1);
  await page.getByRole("button", { name: "统计人数", exact: true }).click();
  await page.getByRole("button", { name: "更新客群", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "客群名称" })).toHaveValue("测试客群");
  await page.getByRole("button", { name: "确认更新", exact: true }).click();
  await expect(page.getByText("已更新客群《测试客群》", { exact: true })).toBeVisible();
  expect(requests.at(-1).name).toBe("测试客群");
  await expect(page.getByRole("button", { name: "打开客群", exact: true })).toBeVisible();
  expect(page.url()).not.toContain("groupId=90");
});
test("切换标签库清空选择与输入框上下文", async ({ page }) => {
  await page.goto("/agent-ui/"); await showTags(page);
  await page.getByRole("checkbox", { name: "选择目录：客户经营", exact: true }).click();
  await page.getByRole("button", { name: "加入输入框" }).click();
  await page.getByRole("button", { name: "当前标签库", exact: true }).click();
  await page.getByRole("option", { name: "公司客户经营标签库", exact: true }).click();
  await expect(page.locator(".composer-tags")).toHaveCount(0);
  await expect(page.getByText("已选 0 / 5 项")).toBeVisible();
  await expect(page.getByText("当前库暂无已发布且可执行的标签")).toBeVisible();
});
