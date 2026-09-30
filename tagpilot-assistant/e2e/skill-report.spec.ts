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
    run_profile: 'skill',
    plan: { revision: 2, hash: 'h', valid: true, plan_status: 'READY', tree: { kind: 'TAG_PREDICATE', clause_id: 'a', tag_id: 1, name: '客户余额', operator: '>', values: ['0'], status: 'BOUND', allowed_operators: ['>'], candidates: [] } },
    count: { value: 240, revision: 2, plan_hash: 'h' },
    messages: [{ id: 'u', role: 'user', text: '分析这批客户', created_at: '2026-09-30T00:00:00Z' },
      { id: 'a', role: 'assistant', text: '分析正文。', created_at: '2026-09-30T00:00:01Z' }],
    versions: [], events: [], capabilities: { count: true, preview: false, create: false, insight: true },
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
