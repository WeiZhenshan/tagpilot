import { test, expect } from "@playwright/test";

// 合成会话只验证消息、处理记录和确认表单的位置，不调用模型或业务接口。
for (const { width, profile } of [1440, 390].flatMap((width) =>
  ["audience", "conversation"].map((profile) => ({ width, profile })))) {
  test(`处理记录与确认卡片跟随所属输入（${width}px，${profile}）`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 960 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const message = (id: string, role: string, run_id: string, text: string) => ({
      id, role, run_id, text, created_at: "2026-10-23T01:00:00Z",
    });
    const thread = {
      thread_id: "turns", title: "多轮位置测试", library_id: 107,
      archived: false, pinned: false, revision: 0, versions: [],
      capabilities: { count: false, create: false, preview: false },
      status: "WAITING", run_id: "second", run_profile: profile,
      interrupt_id: "choose-tag", questions: [{ prompt: "采用哪个客户等级标签？", options: ["最高客户等级", "潜力等级"] }],
      messages: [
        message("u1", "user", "first", "圈选近30天转入客户"),
        message("a1", "assistant", "first", "已保留转入条件。"),
        message("u2", "user", "second", "再加上高价值客户"),
        message("a2", "assistant", "second", "请确认客户等级口径。"),
        { ...message("u3", "user", "second", "采用最高客户等级"), run_id: undefined },
        message("a3", "assistant", "second", "请选择客户等级档位。"),
      ],
      run_history: [{ run_id: "first", events: [{ seq: 1, type: "run.completed", message: "已完成转入条件" }] }],
      events: [
        { seq: 1, type: "narration", text: "正在核对高价值客户标签" },
        { seq: 2, type: "run.waiting", message: "等待选择客户等级" },
        { seq: 3, type: "run.started", message: "正在处理已确认的客户等级" },
        { seq: 4, type: "run.waiting", message: "等待选择等级档位" },
      ],
    };
    await page.route("**/dev-api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/getInfo")) return route.fulfill({ json: { code: 200, user: { userId: 2, userName: "demo" } } });
      if (path.endsWith("/library/list")) return route.fulfill({ json: { code: 200, rows: [{ libraryId: 107, libraryName: "个人客户经营标签库" }] } });
      if (path.endsWith("/tags/tree")) return route.fulfill({ json: { code: 200, data: [] } });
      if (path.endsWith("/threads")) return route.fulfill({ json: { code: 200, data: [{ threadId: "turns", title: thread.title, libraryId: 107, archived: "0" }] } });
      if (path.endsWith("/resume")) {
        thread.messages.push({ ...message("u4", "user", "second", route.request().postDataJSON().answer), run_id: undefined });
        thread.status = "RUNNING";
        thread.questions = [];
      }
      if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: `event: state\ndata: ${JSON.stringify(thread)}\n\n` });
      return route.fulfill({ json: { code: 200, data: thread } });
    });
    await page.goto("/agent-ui/?threadId=turns");
    const first = page.locator('.conversation-turn[data-message-id="u1"]');
    const second = page.locator('.conversation-turn[data-message-id="u2"]');
    const third = page.locator('.conversation-turn[data-message-id="u3"]');
    await expect(first.getByRole("region", { name: "第 1 轮处理记录", exact: true })).toBeVisible();
    await expect(second.getByRole("region", { name: "第 2 轮处理记录", exact: true })).toBeVisible();
    await expect(third.getByRole("region", { name: "第 3 轮处理记录", exact: true })).toBeVisible();
    await expect(third.locator(".ask-card")).toBeVisible();
    await expect(second.locator(".ask-card")).toHaveCount(0);
    await expect(first.locator(".ask-card")).toHaveCount(0);
    await expect(second.locator(".run-heading")).toContainText("已继续处理");
    await expect(second.locator(".run-heading")).toHaveAttribute("aria-expanded", "false");
    expect(await page.locator(".thread-viewport").evaluate((viewport) =>
      Array.from(viewport.querySelectorAll(".conversation-turn, .run-timeline")).map((node) => node.getAttribute("data-message-id") || node.getAttribute("aria-label"))
    )).toEqual(["u1", "第 1 轮处理记录", "a1", "u2", "第 2 轮处理记录", "a2", "u3", "第 3 轮处理记录", "a3"]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (profile === "audience") await page.screenshot({ path: testInfo.outputPath("waiting.png"), animations: "disabled" });
    const choice = third.getByRole("button", { name: "最高客户等级", exact: true });
    await choice.focus();
    await page.keyboard.press("Enter");
    await third.getByRole("button", { name: "提交并继续" }).click();
    const fourth = page.locator('.conversation-turn[data-message-id="u4"]');
    await expect(fourth.getByRole("region", { name: "第 4 轮处理记录", exact: true })).toBeVisible();
    await expect(fourth.locator(".run-heading")).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator(".ask-card")).toHaveCount(0);
    await expect(third.locator(".run-heading")).toContainText("已继续处理");
    await page.reload();
    await expect(fourth.getByRole("region", { name: "第 4 轮处理记录", exact: true })).toBeVisible();
  });
}
