import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const report = {
  schema_version: 1, run_id: 'skill-run-1', level: 'L2',
  cohort: { audience_id: 'skill-report-fixture', audience_name: '合成测试客群', library_id: 107, revision: 2, plan_hash: 'h', snapshot_id: 'snapshot',
    count: 240, data_as_of: '2026-09-30', reference_date: '2026-09-30', binding_version: '未接入指标绑定',
    declared_context: '分析这批客户的特点', synthetic: false },
  results: [{
    skill_id: 'fact-analysis', display_name: '客群基础事实分析', skill_version: '1.0.0', pack_hash: 'a'.repeat(64),
    registry_version: null, definition_hash: null, level: 'L2', status: 'PARTIAL',
    reasons: ['本轮未接入指标数据'],
    facts: [{ id: 'f-count', metric: 'customer_count', label: '客群规模', value: 240, unit: '人', sample_size: 240, status: 'AVAILABLE',
      query_id: 'cohort.count', evidence: ['服务端核验人数'], role: 'OBSERVED', denominator_id: null, derived_from: [], exclusions_applied: [] }],
    cards: [{ id: 'card-overview', title: '客群概况',
      facts: { text: '本客群由已核验条件圈定，共 {fact:f-count}。', fact_ids: ['f-count'] },
      comparison: { text: '本轮未接入基准数据，无法对比。', fact_ids: [], benchmark_fact_ids: [], difference_fact_ids: [] },
      diagnosis: { text: '缺少对比对象，本轮未形成诊断。', fact_ids: [], basis: 'RULE', statistical_evidence: null },
      action: { text: '本轮不产出行动对象。', fact_ids: [], population_fact_id: null, priority: 'NONE' },
      boundary: { text: '结论仅覆盖客群条件与规模。', data_as_of: '2026-09-30', skill_version: '1.0.0', sample_fact_id: 'f-count',
        metric_definitions: ['customer_count：按当前已核验方案服务端统计的客户数'] } }],
    charts: [{ schema_version: 1, id: 'chart-scale', title: '客群规模', kind: 'kpi', intent: 'single_value', unit: '人', metric_label: '客户数',
      series: [{ name: '客群规模', fact_ids: ['f-count'], points: [{ category: '客户数', column: null, fact_id: 'f-count', value: 240 }] }],
      annotations: [], reconcile: [], zero_baseline: true, orientation: 'vertical' }],
    followups: ['接入指标数据后可分析资产与产品结构'],
  }],
};

test.beforeEach(async ({ page }) => {
  const thread = { thread_id: 'skill-report-fixture', title: '合成测试客群', library_id: 107, status: 'COMPLETED', revision: 2, archived: false, pinned: false,
    run_profile: 'skill', run_id: 'skill-run-1',
    plan: { revision: 2, hash: 'h', valid: true, plan_status: 'READY', tree: { kind: 'TAG_PREDICATE', clause_id: 'a', tag_id: 1, name: '客户余额', operator: '>', values: ['0'], status: 'BOUND', allowed_operators: ['>'], candidates: [] } },
    count: { value: 240, revision: 2, plan_hash: 'h' },
    messages: [{ id: 'u0', role: 'user', run_id: 'audience-run', text: '圈定这批客户', created_at: '2026-09-30T00:00:00Z' },
      { id: 'a0', role: 'assistant', run_id: 'audience-run', text: '圈选完成。', created_at: '2026-09-30T00:00:01Z' },
      { id: 'u', role: 'user', run_id: 'skill-run-1', text: '分析这批客户', created_at: '2026-09-30T00:00:02Z' },
      { id: 'a', role: 'assistant', run_id: 'skill-run-1', text: '分析正文。', created_at: '2026-09-30T00:00:03Z' }],
    run_history: [{ run_id: 'audience-run', events: [{seq: 1, type: 'run.completed'}] }],
    versions: [], events: [{seq: 1, type: 'skill.resource', message: '正在读取技能参考资料'}, {seq: 2, type: 'run.completed'}], capabilities: { count: true, preview: false, create: false, insight: true },
    skill_report: report };
  await page.route('**/dev-api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/getInfo')) return route.fulfill({ json: { code: 200, user: { userId: 2, userName: 'fixture', nickName: '合成测试' } } });
    if (path.endsWith('/library/list')) return route.fulfill({ json: { code: 200, rows: [{ libraryId: 107, libraryName: '合成测试库' }] } });
    if (path.endsWith('/skills/available')) return route.fulfill({ json: { code: 200, data: [] } });
    if (path.endsWith('/tags/tree')) return route.fulfill({ json: { code: 200, data: [] } });
    if (path.endsWith('/threads')) return route.fulfill({ json: { code: 200, data: [] } });
    await route.fulfill({ json: { code: 200, data: thread } });
  });
});

for (const width of [1019, 1440, 390]) test(`左右工作栏动效 ${width}：距离、进退节奏、反向切换`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-report-fixture');
  await expect(page.locator('.insight-report-header')).toBeAttached();
  for (const [selector, buttonClass, sign] of [['.history-rail', '.topbar .sidebar-toggle:not(.report-panel-toggle)', -1], ['.insight-right', '.report-panel-toggle', 1]] as const) {
    const panel = page.locator(selector), toggle = page.locator(buttonClass);
    if (await toggle.getAttribute('aria-expanded') === 'true') {
      await toggle.click(); await expect(panel).not.toBeVisible();
    }
    await panel.evaluate((element) => {
      const node = element as HTMLElement & { motionSamples?: any[] };
      node.motionSamples = [];
      node.addEventListener('transitionrun', (event) => {
        if ((event as TransitionEvent).propertyName !== 'transform' || event.target !== element) return;
        const animation = element.getAnimations().find((item) => (item as CSSTransition).transitionProperty === 'transform');
        if (!animation?.effect) return;
        const timing = animation.effect.getTiming();
        // 百分比 transform 在关键帧中保留表达式，按浏览器实际解析的矩阵测量。
        const currentTime = animation.currentTime;
        animation.currentTime = 0;
        const from = new DOMMatrixReadOnly(getComputedStyle(element).transform).m41;
        animation.currentTime = Number(timing.duration);
        const to = new DOMMatrixReadOnly(getComputedStyle(element).transform).m41;
        animation.currentTime = currentTime;
        const sample = { width: element.getBoundingClientRect().width, entering: !element.hasAttribute('inert'),
          duration: timing.duration, easing: getComputedStyle(element).transitionTimingFunction,
          from, to, overflow: false };
        node.motionSamples!.push(sample);
        const watch = () => {
          sample.overflow ||= document.documentElement.scrollWidth > innerWidth;
          if (animation.playState === 'running') requestAnimationFrame(watch);
        };
        requestAnimationFrame(watch);
      });
    });
    await toggle.click();
    await expect(panel).toBeVisible();
    await expect.poll(() => panel.evaluate((element) => element.getAnimations().length)).toBe(0);
    await toggle.click();
    await expect(panel).toHaveAttribute('inert', '');
    await expect(panel).not.toBeVisible();
    const samples = await panel.evaluate((element) => (element as HTMLElement & { motionSamples: any[] }).motionSamples);
    const enter = samples.find((sample: any) => sample.entering), exit = samples.find((sample: any) => !sample.entering);
    expect(enter).toBeTruthy(); expect(exit).toBeTruthy();
    expect(exit.duration).toBeLessThan(enter.duration);
    expect(exit.easing).not.toBe(enter.easing);
    expect(enter.from * sign).toBeGreaterThanOrEqual(12);
    expect(enter.from * sign).toBeLessThanOrEqual(32);
    expect(enter.to).toBe(0); expect(exit.to * sign).toBeGreaterThan(0);
    expect(exit.width).toBeCloseTo(enter.width, 2);
    expect(Math.abs(exit.to)).toBeCloseTo(Math.abs(enter.from), 2);
    expect(samples.some((sample: any) => sample.overflow)).toBe(false);
    if (process.env.CAPTURE_DIR) { fs.mkdirSync(process.env.CAPTURE_DIR, {recursive:true}); fs.writeFileSync(`${process.env.CAPTURE_DIR}/motion-${selector.slice(1)}-${width}.json`, JSON.stringify(samples, null, 2)); }
    // 在进入尚未结束时再次关闭：最终状态必须以最后一次操作为准。
    await toggle.click(); await toggle.click();
    await expect(panel).not.toBeVisible();
    await expect.poll(() => panel.evaluate((element) => element.getAnimations().length)).toBe(0);
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    if (selector === '.insight-right' && width === 390) {
      await toggle.click();
      await page.locator('.insight-sidebar-heading').getByRole('button', {name: '圈选方案', exact: true}).click();
      await toggle.click();
      // 收起方案时保留面板内容，不能先隐藏子面板再让空壳退出。
      expect(await page.locator('.insight-right .plan-panel').evaluate((element) => getComputedStyle(element).display)).toBe('flex');
      await expect(panel).not.toBeVisible();
    }
  }
});

for (const width of [1019, 390]) test(`减少动态效果 ${width}：左右工作栏直接切换且不能聚焦隐藏内容`, async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({width, height: 844});
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-report-fixture');
  for (const [selector, buttonClass] of [['.history-rail', '.topbar .sidebar-toggle:not(.report-panel-toggle)'], ['.insight-right', '.report-panel-toggle']]) {
    const panel = page.locator(selector), toggle = page.locator(buttonClass);
    if (await toggle.getAttribute('aria-expanded') === 'true') await toggle.click();
    await toggle.click(); await expect(panel).toBeVisible();
    expect(await panel.evaluate((element) => ({ animations: element.getAnimations().length, transform: getComputedStyle(element).transform }))).toEqual({animations: 0, transform: 'none'});
    await toggle.click(); await expect(panel).not.toBeVisible();
    await expect(panel).toHaveAttribute('inert', '');
    await expect(toggle).toBeFocused();
  }
  await page.emulateMedia({reducedMotion: 'no-preference'});
  await page.locator('.report-panel-toggle').click();
  await page.emulateMedia({reducedMotion: 'reduce'});
  expect(await page.locator('.insight-right').evaluate((element) => element.getAnimations().length)).toBe(0);
});

for (const width of [1019, 390]) test(`报告入口 ${width}：收起、重新打开与重复定位`, async ({ page }) => {
  await page.setViewportSize({ width, height: 763 });
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-report-fixture');
  if (width === 390) await page.getByRole('tab', {name: '洞察', exact: true}).click();
  await expect(page.locator('.insight-report')).toBeVisible();
  await expect(page.getByRole('button', {name: '宽模式', exact: true})).toHaveCount(0);
  const toggle = page.locator('.report-panel-toggle');
  await expect(toggle).toHaveCount(1);
  await expect(page.getByRole('button', {name: '收起右侧面板', exact: true})).toHaveCount(0);
  await page.getByRole('button', {name: '隐藏右侧面板', exact: true}).click();
  await expect(page.locator('.insight-right')).not.toBeVisible();
  await toggle.press('Space');
  await expect(page.locator('.insight-report')).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await toggle.press('Enter');
  await expect(page.locator('.insight-right')).not.toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', {name: '展开洞察报告', exact: true}).click();
  await expect(page.locator('.insight-report')).toBeVisible();
  await expect(page.getByRole('button', {name: '隐藏右侧面板', exact: true})).toHaveAttribute('aria-expanded', 'true');
  // 面板滚动后，再次从摘要打开会回到报告开头并取得键盘焦点。
  await page.locator('.insight-report').evaluate((element) => { element.scrollTop = 300; });
  const readingPosition = await page.locator('.insight-report').evaluate((element) => element.scrollTop);
  await toggle.click();
  await expect(page.locator('.insight-right')).not.toBeVisible();
  await toggle.click();
  await expect(page.locator('.insight-report')).toBeVisible();
  await expect.poll(() => page.locator('.insight-report').evaluate((element) => element.scrollTop)).toBe(readingPosition);
  if (width === 1019) {
    await page.getByRole('button', {name: '展开洞察报告', exact: true}).click();
    await expect.poll(() => page.locator('.insight-report').evaluate((element) => element.scrollTop)).toBe(0);
  }
  await page.locator('#agent-right-panel').press('Escape');
  await expect(page.locator('.insight-right')).not.toBeVisible();
  await expect(page.getByRole('button', {name: '展开右侧面板', exact: true})).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('两轮处理记录与技能报告分别归属对应需求和答复', async ({ page }) => {
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-report-fixture');
  const first = page.locator('.conversation-turn[data-message-id="u0"]');
  const second = page.locator('.conversation-turn[data-message-id="u"]');
  await expect(first.getByRole('region', {name: '第 1 轮处理记录'})).toBeVisible();
  await expect(second.getByRole('region', {name: '第 2 轮处理记录'})).toContainText('技能分析已完成');
  await second.locator('.run-heading').click();
  await expect(second).toContainText('正在读取技能参考资料');
  await expect(page.locator('.conversation-turn[data-message-id="a"] .insight-summary')).toContainText('洞察已保存');
  await page.reload();
  await expect(first.locator('.run-timeline')).toHaveCount(1);
  await expect(second.locator('.run-timeline')).toHaveCount(1);
});

for (const width of [1440, 390]) test(`技能报告展示 ${width}：面板自动切换、卡片、KPI 与边界`, async ({ page }) => {
  await page.setViewportSize({ width, height: width === 390 ? 844 : 960 });
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-report-fixture');
  if (width === 390) await page.getByRole('tab', { name: '洞察' }).click();
  const panel = page.locator('.insight-report');
  await expect(panel).toBeVisible();
  await expect(panel.locator('.insight-report-header')).toContainText('合成测试客群');
  await expect(panel.locator('.insight-report-header')).toContainText('240 人');
  await expect(panel.locator('.insight-boundary').first()).toContainText('部分洞察可用');
  await expect(panel.locator('.insight-kpi')).toHaveText('240人');
  await expect(panel.locator('.insight-findings h3')).toHaveText('客群概况');
  await expect(panel.locator('.insight-findings')).toContainText('本客群由已核验条件圈定，共 240人。');
  await expect(panel.locator('.insight-findings')).toContainText('缺少对比对象，本轮未形成诊断。');
  await expect(panel.locator('.insight-followups')).toContainText('接入指标数据后可分析资产与产品结构');
  await expect(panel.locator('.insight-feedback')).toHaveCount(0);
  await expect(page.locator('.insight-summary')).toContainText('洞察已保存');
  if (process.env.CAPTURE_DIR) {
    fs.mkdirSync(process.env.CAPTURE_DIR, { recursive: true });
    await page.screenshot({ path: `${process.env.CAPTURE_DIR}/skill-report-${width}.png` });
  }
});

test('技能报告在方案变化后标记过期', async ({ page }) => {
  await page.route('**/dev-api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/getInfo')) return route.fulfill({ json: { code: 200, user: { userId: 2, userName: 'fixture', nickName: '合成测试' } } });
    if (path.endsWith('/library/list')) return route.fulfill({ json: { code: 200, rows: [{ libraryId: 107, libraryName: '合成测试库' }] } });
    if (path.endsWith('/skills/available')) return route.fulfill({ json: { code: 200, data: [] } });
    if (path.endsWith('/tags/tree')) return route.fulfill({ json: { code: 200, data: [] } });
    if (path.endsWith('/threads')) return route.fulfill({ json: { code: 200, data: [] } });
    await route.fulfill({ json: { code: 200, data: { thread_id: 'skill-report-fixture', title: '合成测试客群', library_id: 107, status: 'COMPLETED', revision: 5, archived: false, pinned: false,
      run_profile: 'skill', plan: { revision: 5, hash: 'h2', valid: true }, count: { value: 240, revision: 5, plan_hash: 'h2' }, messages: [], versions: [], events: [],
      capabilities: { count: true, preview: false, create: false, insight: true }, skill_report: report } } });
  });
  await page.goto('/agent-ui/?libraryId=107&threadId=skill-report-fixture');
  const panel = page.locator('.insight-report');
  await expect(panel.locator('.insight-boundary').filter({ hasText: '已过期' })).toBeVisible();
  await expect(panel.getByRole('button', { name: '复制本段摘要' })).toBeDisabled();
});
