# TagPilot 智能体工作台 · 右侧栏交互反馈评审

- 日期：2026-11-11
- 范围：`tagpilot-assistant` 右栏（圈选方案 / 洞察报告）的操作感知与视觉反馈，不评业务正确性
- 方法：源码评审（组件 + CSS 全量核对）。:5174 可访问，但工作台依赖登录态，未花时间登录；结论均可由 `src/` 源码复核
- 对照基准：`tagpilot-assistant/DESIGN.md`（现有设计立场）

## 1. 现象总述

右栏的问题不是"缺装饰"，而是**缺一层状态语言**。DESIGN.md 为每个组件定义了 default / hover / selected / disabled 的静态颜色（[DESIGN.md:190-195](../../tagpilot-assistant/DESIGN.md)），也明确"悬停只变背景、0.15s、无位移动画、无 box-shadow"；但它没有为**按下、等待中、结构变化、进行中**这四种瞬时状态定义任何表达。于是所有交互都只剩"颜色换一下"：

1. **点击没有任何按下反馈**。全仓库唯一的 `:active` 规则在分隔手柄上（[index.css:1529](../../tagpilot-assistant/src/index.css:1529)、[index.css:1551](../../tagpilot-assistant/src/index.css:1551)），普通按钮、主按钮、tab、图标按钮全部没有 pressed 态。
2. **异步操作用"变灰"代替了"进行中"**。统计、保存核验、创建、改图、反馈共用全局 `pending`，但右栏没有任何 spinner 或文案变化（[App.tsx:424-439](../../tagpilot-assistant/src/App.tsx:424)、[PlanPanel.tsx:93](../../tagpilot-assistant/src/PlanPanel.tsx:93)）。用户点完按钮看到的是按钮变灰、页面无变化——正是"没反应"。
3. **结构性变化都是裸 mount**。tab 切换是三元表达式整块替换（[App.tsx:1032-1071](../../tagpilot-assistant/src/App.tsx:1032)），条件编辑器、创建确认区、图表画布全部瞬时出现/消失。唯一的入场动画是面板整体的 `inert` 进出场（[panel-motion.css:12-46](../../tagpilot-assistant/src/panel-motion.css:12)），tab 切换和 `reportReveal` 都绕过了它。
4. **右栏宽度在 tab 间直接从 370px 跳到 clamp(370px, 44vw, 620px)**（[workbench-insight.css:6](../../tagpilot-assistant/src/insight/workbench-insight.css:6)、[workbench-insight.css:12](../../tagpilot-assistant/src/insight/workbench-insight.css:12)），中栏随之瞬时重排。这是右栏最"重"的一次跳变。
5. **层次只剩 1px 线**。右栏底色 `#fcfcfd` 与中栏 `#fff` 相差 3 个灰阶（[workbench-insight.css:6](../../tagpilot-assistant/src/insight/workbench-insight.css:6)），报告内部没有卡片、没有吸顶、没有滚动阴影，因此"像一张纸"。

## 2. 交互元素状态矩阵

图例：✅ 存在且可感知；△ 存在但弱/无过渡；— 不存在；n/a 不适用。

| 元素 | default | hover | focus-visible | pressed/active | selected/expanded | disabled | loading |
|---|---|---|---|---|---|---|---|
| 右栏两个 tab（[App.tsx:1032](../../tagpilot-assistant/src/App.tsx:1032)） | ✅ | △ 仅底色 | ✅ | — | △ 仅底色、无指示条 | n/a | n/a |
| 主按钮 `.primary`（[index.css:1108](../../tagpilot-assistant/src/index.css:1108)） | ✅ | ✅ 加深 | ✅ | — | n/a | △ 全局灰 | — |
| 普通按钮 / 图标按钮 | ✅ | ✅ | ✅ | — | △ `aria-expanded` 仅改背景 | △ 全局灰 | — |
| `.text-button`（[index.css:356](../../tagpilot-assistant/src/index.css:356)） | ✅ | △ 0.15s 底色 | ✅ | — | n/a | △ 变灰块 | — |
| 条件行图标（编辑/口径）（[index.css:939](../../tagpilot-assistant/src/index.css:939)） | ✅ | ✅ | ✅ | — | △ 展开时浅底 | ✅ | n/a |
| 比较方式 / 条件值 / 码值选择器（[ListboxSelect.tsx:182](../../tagpilot-assistant/src/ListboxSelect.tsx:182)） | ✅ | ✅ | ✅ | — | — 展开态无视觉，仅 chevron 翻转 | ✅ | n/a |
| 数值输入框 | ✅ | — | ✅ | — | — 无"已修改"态 | ✅ | n/a |
| 条件编辑区 / 创建确认区 | ✅ | n/a | ✅ | n/a | — 裸 mount | ✅ | n/a |
| 历史版本项（[PlanMenu.tsx:50](../../tagpilot-assistant/src/PlanMenu.tsx:50)） | ✅ | ✅ | ✅ | — | △ 浅底 + 主色边 | ✅ | n/a |
| `重新统计` / `创建客群` / `保存并核验` | ✅ | ✅ | ✅ | — | 可用性切换 △ | ✅ | — |
| 报告分段按钮（[insight.css:9](../../tagpilot-assistant/src/insight/insight.css:9)） | ✅ | ✅ | ✅ | — | △ 仅底色 | n/a | n/a |
| `核验并应用` / `保存反馈` / `重跑` | ✅ | ✅ | ✅ | — | n/a | ✅ 灰 | — |
| 图表导出按钮（[InsightChart.tsx:130](../../tagpilot-assistant/src/insight/InsightChart.tsx:130)） | ✅ | ✅ | △ 依赖全局 | — | n/a | ✅ | — |
| `<details>` 折叠（[insight.css:28](../../tagpilot-assistant/src/insight/insight.css:28)） | ✅ | n/a | ✅ | n/a | △ 原生三角 | n/a | n/a |
| 右栏分隔手柄（[index.css:1507](../../tagpilot-assistant/src/index.css:1507)） | ✅ 1px 线 | ✅ 3px 线 + 握把 | ✅ | △ 与 hover 相同 | n/a | ✅ `aria-disabled` | — 拖拽中无读数 |
| 右栏面板进出（[panel-motion.css](../../tagpilot-assistant/src/panel-motion.css)） | ✅ | n/a | n/a | n/a | ✅ 200ms/120ms | n/a | n/a |

整体看：**pressed 与 loading 两列几乎全是"—"**，这就是"我做了操作但没有感觉"的根因。

## 3. 发现清单

### P0 —— 用户明确感知"没反应"

#### P0-1 所有按钮都没有按下态
- 位置：[index.css:32-49](../../tagpilot-assistant/src/index.css:32)、[index.css:1108-1115](../../tagpilot-assistant/src/index.css:1108)
- 现状：`button` 只有 `transition: background .15s` 与 hover 变灰，`:active` 规则全仓库只存在于 split-handle。主按钮 hover 变深、按下与 hover 完全相同。
- 感知：点击"统计人数""创建客群""保存并核验""核验并应用"时手指/鼠标没有任何触觉确认；在结果回来前，用户无法判断点击是否生效。

#### P0-2 异步操作只有"禁用"，没有"进行中"
- 位置：[PlanPanel.tsx:93](../../tagpilot-assistant/src/PlanPanel.tsx:93)（进度条只在 `running || WAITING` 出现，不覆盖客户端 `pending`）、[PlanPanel.tsx:99](../../tagpilot-assistant/src/PlanPanel.tsx:99)（重新统计）、[PlanPanel.tsx:113-125](../../tagpilot-assistant/src/PlanPanel.tsx:113)（保存/创建）、[InsightReportPanel.tsx:57-58](../../tagpilot-assistant/src/insight/InsightReportPanel.tsx:57)（改图/反馈）
- 现状：`operation()` 期间 `pending=true`，`disabled` 置灰所有按钮，但按钮文案不变、无 spinner、`plan-status` 仍显示"已核验"（[PlanPanel.tsx:63](../../tagpilot-assistant/src/PlanPanel.tsx:63)）。只有全局错误横幅会在失败时出现（[App.tsx:432](../../tagpilot-assistant/src/App.tsx:432)）。
- 感知：统计人数通常要数秒；这几秒里按钮只是"变灰"，状态胶囊还停留在旧值，像卡死。失败时错误横幅出现在**中栏顶部**（[App.tsx:941-953](../../tagpilot-assistant/src/App.tsx:941)），离刚点的按钮一屏之隔，右栏本地没有任何失败回执。

#### P0-3 洞察 tab 在分析进行中显示错误的空状态
- 位置：[App.tsx:1053-1071](../../tagpilot-assistant/src/App.tsx:1053)
- 现状：右栏内容优先级是 `activeAnalysisMessage → skillReport → thread.insight_report → 空状态`。技能运行中这三者都可能为空，于是 `rightTab === "insight"` 时显示"在对话框输入 /，选择已发布技能并携带当前客群开始分析"（[App.tsx:1071](../../tagpilot-assistant/src/App.tsx:1071)）——用户刚刚点了分析。
- 感知：用户点击"洞察"后看到一句"请开始分析"的引导，等同"我做的操作没被记录"。

### P1 —— 反馈弱、状态切换跳变

#### P1-1 tab 切换没有指示条动画，选中只有底色
- 位置：[workbench-insight.css:7-13](../../tagpilot-assistant/src/insight/workbench-insight.css:7)、[App.tsx:1032](../../tagpilot-assistant/src/App.tsx:1032)
- 现状：两个原生 button，`aria-pressed` 映射到 `background:#e8ecf2;color:#17243a`，切换时底色瞬间变化（0.15s background 过渡几乎不可见）。
- 感知：tab 是右栏唯一的模式切换，却比正文里的链接反馈还弱；没有"当前在哪一页"的持续指示（下划线/滑块）。

#### P1-2 tab 内容裸替换 + 右栏宽度瞬时跳变
- 位置：[App.tsx:1033](../../tagpilot-assistant/src/App.tsx:1033)、[workbench-insight.css:6](../../tagpilot-assistant/src/insight/workbench-insight.css:6)、[workbench-insight.css:12](../../tagpilot-assistant/src/insight/workbench-insight.css:12)
- 现状：`rightTab === "plan" ? <PlanPanel/> : <report/>` 整块卸载/挂载，无淡入、无位移；同时 `.insight-right` 从 370px（或用户存的 plan 宽度）变成 `clamp(370px, 44vw, 620px)`，1440px 下净增 250px，中栏对话区同一帧被压缩。
- 感知：点"洞察"的瞬间，整个三栏布局"啪"地重排一次，报告文字同时出现——视觉冲击来自布局而非内容，是右栏最明显的一次跳变。
- 附注：从"圈选方案"切回时，`PlanPanel` 重新挂载，**未保存的草稿静默丢失**（`draft` 是 [PlanPanel.tsx:23](../../tagpilot-assistant/src/PlanPanel.tsx:23) 的局部 state），且没有任何提示。

#### P1-3 `reportReveal` 只有滚动与聚焦，没有视觉
- 位置：[App.tsx:96-103](../../tagpilot-assistant/src/App.tsx:96)、[App.tsx:141-147](../../tagpilot-assistant/src/App.tsx:141)
- 现状：`openRightPanel("insight")` 把 `reportReveal` 加一，效果仅是 `scrollTo({top:0})` 和 `panel.focus()`。若面板已经打开，`inert` 不变，`panel-motion` 也不会触发。
- 感知：从对话里的"展开洞察报告"或摘要卡点击进入时，除了内容换掉，面板没有任何"展开"动作；预期的 200ms 入场只发生在"面板从关闭到打开"这一种路径。

#### P1-4 条件编辑区 / 创建确认区裸 mount，内容瞬移
- 位置：[ClauseSummary.tsx:97](../../tagpilot-assistant/src/ClauseSummary.tsx:97)、[PlanPanel.tsx:116-120](../../tagpilot-assistant/src/PlanPanel.tsx:116)
- 现状：`open ? <ClauseEditor/> : null`；`confirm ? <div className="create-form">...</div> : <>按钮</>`。两者都没高度过渡，点击编辑图标/创建客群后，下方内容整段向下弹开，滚动位置可能跳动。
- 感知：编辑是右栏最高频的动作，每次展开都是一次无过渡的布局位移；在 `max-height:48%` 的 `.plan-actions`（[index.css:1098](../../tagpilot-assistant/src/index.css:1098)）里还可能触发内部滚动跳变。

#### P1-5 图表裸 mount；拖拽右栏时图表反复重播动画
- 位置：[InsightChart.tsx:62-80](../../tagpilot-assistant/src/insight/InsightChart.tsx:62)、[echartsAdapter.ts:18-19](../../tagpilot-assistant/src/insight/echartsAdapter.ts:18)
- 现状：图表组件挂载后 `useEffect` 里 `echarts.init` + `setOption({notMerge:true})`，入场只有 ECharts 自身的 180ms 柱体动画；KPI（原生数字）与表格（原生 HTML）完全没有过渡。`ResizeObserver` 每帧回调里都执行 `chart.resize(); update();`，而 `update()` 每次 `notMerge:true` 重设 option——拖动分隔手柄时，柱子会随每一帧重新从 0 长出来。
- 感知：打开报告时画布先空一帧再"自己长出来"；拖宽右栏时图表持续闪烁，与"拖拽调宽"这个动作的意图相冲突。

#### P1-6 "已修改"反馈弱，人数从数字瞬变"—"
- 位置：[PlanPanel.tsx:71](../../tagpilot-assistant/src/PlanPanel.tsx:71)、[PlanPanel.tsx:98-103](../../tagpilot-assistant/src/PlanPanel.tsx:98)、[index.css:987-989](../../tagpilot-assistant/src/index.css:987)
- 现状：第一次编辑后 `dirty=true`，条件行出现 11px 的"改"角标（`.clause-change`），人数区 `<strong>` 从数字直接变成"—"，说明文字换成"修改后须重新核验和统计"；状态胶囊变成"未保存"。
- 感知：用户改一个数值，最显眼的人数数字瞬间消失，却没有任何"刚才改的是这一行"的定位反馈；"改"角标在 370px 宽、13px 正文的行内很容易被忽略。

#### P1-7 移除条件无撤销、无过渡
- 位置：[PlanPanel.tsx:55](../../tagpilot-assistant/src/PlanPanel.tsx:55)、[PlanPanel.tsx:108](../../tagpilot-assistant/src/PlanPanel.tsx:108)、[index.css:998-1000](../../tagpilot-assistant/src/index.css:998)
- 现状：删除后立即从条件树消失，下方追加一条带 `del` 的"已删除"回执；无确认、无撤销、无高度动画。
- 感知：有一次"删了"的书面回执，但操作不可逆、内容跳变；破坏性动作缺少停顿感。

#### P1-8 空状态 CTA 只是普通按钮
- 位置：[workbench-insight.css:23](../../tagpilot-assistant/src/insight/workbench-insight.css:23)、[App.tsx:1071](../../tagpilot-assistant/src/App.tsx:1071)
- 现状：`.insight-empty` 只有 `padding:20px; font-size:13px; color:var(--muted)`；"选择技能"按钮走全局白底描边样式，贴在左上角。
- 感知：右栏主体是"接下来做什么"的唯一入口，却与普通文字按钮同级，视觉上没有号召力。

#### P1-9 右栏与中栏的层次几乎不可见
- 位置：[workbench-insight.css:6](../../tagpilot-assistant/src/insight/workbench-insight.css:6)、[insight.css:5-24](../../tagpilot-assistant/src/insight/insight.css:5)
- 现状：中栏 `#fff`、右栏 `#fcfcfd`，分界只靠分隔手柄里 1px 的 `--border`（#e7e9ed）；报告内部全部靠 `border-bottom` 分隔，没有卡片、没有吸顶标题。
- 感知：报告读起来"像一张纸"，滚动时标题消失、层次只剩横线；这正是用户所说"平面化"的直接来源之一。

#### P1-10 分隔手柄拖拽中与 hover 无区别
- 位置：[SplitHandle.tsx:29-64](../../tagpilot-assistant/src/SplitHandle.tsx:29)、[index.css:1517-1553](../../tagpilot-assistant/src/index.css:1517)
- 现状：hover / focus / `:active` 共用同一组样式（3px 线 + 握把显现）；拖拽期间唯一的额外反馈是 `body.split-resizing` 的全局 `col-resize` 光标。没有宽度读数，没有"正在调整"的强调色。
- 感知：按住拖动时手柄外观不变，用户无法确认"正在拖"与"只是悬停"的区别；键盘用户按方向键有 `aria-valuenow`，视觉与鼠标用户却看不到数值。

#### P1-11 历史版本切换瞬时，缺少上下文
- 位置：[PlanMenu.tsx:50-57](../../tagpilot-assistant/src/PlanMenu.tsx:50)、[PlanPanel.tsx:92](../../tagpilot-assistant/src/PlanPanel.tsx:92)
- 现状：在弹窗里点一个版本 → 弹窗关闭 → 右栏条件树整段替换为旧版本，只多一条"你正在查看 vX 返回当前"的提示条；无过渡，退回当前版本时也没有"从哪个版本返回"的视觉锚点。
- 感知：一次跨版本的大幅内容变化没有任何过渡锚点，用户容易怀疑"是不是点错了"。

#### P1-12 反馈表单埋底、没有 👍/👎 快速件
- 位置：[InsightReportPanel.tsx:58](../../tagpilot-assistant/src/insight/InsightReportPanel.tsx:58)、[workbench-insight.css:24-25](../../tagpilot-assistant/src/insight/workbench-insight.css:24)
- 现状：反馈是一个 1–5 分 `<select>` + textarea + "保存反馈"，排在长报告最底部、导出按钮之后，无边框无背景；提交后只有纯文本 notice。
- 感知：想做"这条洞察有用"的轻量反馈需要展开下拉、选择、再点保存；没有"赞/踩"的一键反馈，也没有"已记录"的即时确认。

### P2 —— 细节

| # | 位置 | 现象 |
|---|---|---|
| P2-1 | [index.css:45-48](../../tagpilot-assistant/src/index.css:45) vs [index.css:356](../../tagpilot-assistant/src/index.css:356) | `.text-button` 被禁用时套用全局 `button:disabled` 背景，变成灰块，与文档式按钮语义不符 |
| P2-2 | [ListboxSelect.tsx:182-198](../../tagpilot-assistant/src/ListboxSelect.tsx:182) | 选择器展开时触发器无边框/底色变化，只有 chevron 翻转，`aria-expanded` 无视觉对应 |
| P2-3 | [insight.css:28-29](../../tagpilot-assistant/src/insight/insight.css:28)、[index.css:1066-1077](../../tagpilot-assistant/src/index.css:1066) | `<details>` 用浏览器默认 marker，各端样式不一，展开无动画 |
| P2-4 | [index.css:38](../../tagpilot-assistant/src/index.css:38)、[workbench-insight.css:8](../../tagpilot-assistant/src/insight/workbench-insight.css:8) | tab 按钮高度约 37px，低于 44px 触控目标 |
| P2-5 | [App.tsx:1032](../../tagpilot-assistant/src/App.tsx:1032) vs [App.tsx:917-940](../../tagpilot-assistant/src/App.tsx:917) | 右栏 tab 用 `aria-pressed`，移动端同一组切换却用 `tablist/tab` + `aria-selected`，两套语义 |
| P2-6 | [workbench-insight.css:15](../../tagpilot-assistant/src/insight/workbench-insight.css:15) | 报告滚动区无吸顶标题、无滚动阴影，长报告滚动时失去位置感 |
| P2-7 | [InsightChart.tsx:130](../../tagpilot-assistant/src/insight/InsightChart.tsx:130) | 导出 SVG/PNG 只有禁用态，无"导出中…"文案，大图导出可能数秒 |
| P2-8 | [AnalysisMessageParts.tsx:24](../../tagpilot-assistant/src/insight/AnalysisMessageParts.tsx:24) | 聊天内图表分类可点击（`onSelectCategory`），但画布本身无 `cursor:pointer` 提示；报告内图表又不可点，两处行为不一致 |
| P2-9 | [index.css:938](../../tagpilot-assistant/src/index.css:938) | 状态胶囊"未保存/待核验/已核验"切换无强调，`role=status` 对读屏可见但对视觉无变化 |
| P2-10 | [InsightReportPanel.tsx:57-59](../../tagpilot-assistant/src/insight/InsightReportPanel.tsx:57) | 操作结果 notice 是裸 `<p>`，位于两个表单之后的报告底部，与刚操作的位置相隔较远，容易被忽略 |
| P2-11 | [insight.css:9-10](../../tagpilot-assistant/src/insight/insight.css:9)、[workbench-insight.css:7-13](../../tagpilot-assistant/src/insight/workbench-insight.css:7) | 报告内"资产结构/产品缺口/机会排序"分段与顶部"圈选方案/洞察"tab 是两套视觉语言，且都只有底色选中 |

## 4. 右栏交互反馈优化建议

设计约束保持：不加装饰性动效、不做无依据的完成状态、保留 reduced-motion 与 focus 可见性。以下数值可直接落地。

### 4.1 动效与层级 token（先建语言，再改组件）

在 `panel-motion.css` 或新 `motion.css` 中补充：

```css
:root {
  --motion-press: 70ms;
  --motion-fast: 120ms;
  --motion-base: 180ms;
  --motion-panel: 220ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-emphasis: cubic-bezier(0.2, 0.8, 0.2, 1);

  /* 只给"浮在页面上"的瞬态层，静态面板仍然无阴影 */
  --elevation-1: 0 1px 2px rgb(23 36 58 / 6%), 0 1px 1px rgb(23 36 58 / 4%);
  --elevation-2: 0 6px 16px rgb(23 36 58 / 10%), 0 1px 3px rgb(23 36 58 / 6%);
  --elevation-3: 0 18px 44px rgb(23 36 58 / 16%);
}
```

- 现有代码其实已经破了"无 box-shadow"的约定：`.library-options`（[index.css:166](../../tagpilot-assistant/src/index.css:166)）与 `.scroll-bottom`（[index.css:867](../../tagpilot-assistant/src/index.css:867)）都有投影。建议把 DESIGN.md 的立场改成"**静态面板无投影；瞬态/浮层使用 elevation 1–3**"，与现状一致。
- 落点：`library-options` / `plan-menu-options` / `clause-info` → `elevation-2`；dialog/移动覆盖面板 → `elevation-3`；拖拽读数、吸顶标题 → `elevation-1`；条件行、报告卡片仍只用 1px 边框，保持平面。

### 4.2 按下态（解决 P0-1）

```css
button {
  transition: background var(--motion-fast) var(--ease-standard),
              border-color var(--motion-fast) var(--ease-standard),
              color var(--motion-fast) var(--ease-standard);
}
button:active:not(:disabled) {
  transform: translateY(1px);
  transition-duration: var(--motion-press);
}
.primary:active:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 40%, #000);
}
```

- 1px 位移是"状态"不是"装饰"：它只在按住期间存在，不产生布局位移，且 `prefers-reduced-motion` 下可单独关闭（`transform:none`）。若坚持零位移，用 `box-shadow: inset 0 1px 2px rgb(23 36 58 / 18%)` 代替。
- 图标按钮（[index.css:939](../../tagpilot-assistant/src/index.css:939)）同样继承；tab 按钮按下用 `background:#dde3ea` 的加深。

### 4.3 进行中状态（解决 P0-2、P2-7）

- 在 `PlanPanel` / `InsightReportPanel` 内记录"最近一次操作"：`"count" | "save" | "create" | "edit" | "rerun" | "feedback" | null`，与全局 `pending` 组合判断。
- 按钮模板：加载时替换文案 + 12px spinner，保留原宽度避免布局抖动。

```css
button[data-busy="true"] { display: inline-flex; align-items: center; gap: 6px; min-width: 5.5em; justify-content: center; }
button[data-busy="true"]::before {
  content: ""; width: 12px; height: 12px; border-radius: 50%;
  border: 2px solid currentColor; border-right-color: transparent;
  animation: btn-spin 700ms linear infinite;
}
@keyframes btn-spin { to { transform: rotate(360deg); } }
```

- 文案：`统计中…` / `保存中…` / `创建中…` / `核验中…` / `重跑中…` / `提交中…`；按钮加 `aria-busy="true"`，`.plan-panel` 加 `aria-busy`。
- `plan-status` 同步临时显示"统计中/保存中"（数据源见 [PlanPanel.tsx:63](../../tagpilot-assistant/src/PlanPanel.tsx:63)），完成后 300ms 内切回真实状态。
- 分析运行中打开洞察 tab 时（P0-3），用 `.insight-empty` 的加载态替代引导文案："正在生成洞察…" + 已运行时长。

### 4.4 tab 指示条与内容过渡（解决 P1-1、P1-2、P1-3）

指示条（下划线方案，最贴合现有白灰语言）：

```css
.insight-sidebar-heading {
  position: relative;
  display: grid; grid-template-columns: 1fr 1fr;
  padding: 6px 16px 0;
  border-bottom: 1px solid var(--border);
}
.insight-sidebar-heading button {
  background: transparent; border: 0; border-radius: 0;
  padding: 10px 8px; font-weight: 500; color: var(--muted);
}
.insight-sidebar-heading button[aria-pressed="true"] { color: #17243a; font-weight: 600; background: transparent; }
.insight-sidebar-heading::after {
  content: ""; position: absolute; left: 16px; bottom: 0;
  width: calc((100% - 32px) / 2); height: 2px;
  background: var(--accent);
  transform: translateX(0);
  transition: transform var(--motion-base) var(--ease-emphasis);
}
.insight-sidebar-heading[data-tab="insight"]::after { transform: translateX(100%); }
```

容器需补 `data-tab={rightTab}`。若偏好胶囊底，则改为 `background:var(--soft)` 的滑块，`transform:translateX(100%)`，180ms 同缓动。

内容过渡：给右栏主体加 `key={rightTab}` 的包裹层。包裹层必须接管原内容的弹性尺寸，否则会破坏右栏滚动：

```css
.right-pane { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; animation: right-pane-in var(--motion-base) var(--ease-standard); }
@keyframes right-pane-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
```

宽度过渡（注意别和拖拽冲突）：

```css
.insight-right { transition: width var(--motion-panel) var(--ease-emphasis); }
body.split-resizing .insight-right { transition: none; }
@media (prefers-reduced-motion: reduce) { .insight-right { transition: none; } }
```

- 视口跨断点时媒体查询改宽也会动画 220ms，可接受；拖拽期间用 `body.split-resizing` 关掉。
- `reportReveal` 应真正触发一次"面板展开"：若面板已打开，复用 `right-pane-in` 覆盖在内容上（不重复面板位移）；若面板关闭，仍走现有 200ms `inert` 过渡，二者取其一，避免叠加。
- 切 tab 前若 `PlanPanel` 处于 dirty，拦截并提示"有未保存修改，切换将丢弃"，或把草稿提升到 App 层保留。

### 4.5 折叠/展开的高度过渡（解决 P1-4、P1-7）

统一用 grid-rows 过渡（需要保持 DOM 挂载，因此不用 `height:auto`）：

```css
.collapse { display: grid; grid-template-rows: 0fr; opacity: 0; transition: grid-template-rows var(--motion-base) var(--ease-standard), opacity var(--motion-fast) linear; }
.collapse[data-open="true"] { grid-template-rows: 1fr; opacity: 1; }
.collapse > * { overflow: hidden; min-height: 0; }
```

- 条件编辑器（[ClauseSummary.tsx:97](../../tagpilot-assistant/src/ClauseSummary.tsx:97)）与创建确认区（[PlanPanel.tsx:116](../../tagpilot-assistant/src/PlanPanel.tsx:116)）改为常驻挂载 + `data-open` + 关闭时 `inert`；`autoFocus` 等过渡结束后再 `focus({preventScroll:true})`，避免展开瞬间滚动跳。
- 新增条件、删除条件的行高变化也用同一 180ms；删除回执行加"撤销"文本按钮（保留 5 秒），点击恢复上一棵 `tree`。
- 历史版本切换（P1-11）：条件树容器 `key={shown?.revision}` 复用 `right-pane-in` 的 140ms 淡入，提示条从上滑下 8px。

### 4.6 "已修改"定位反馈（解决 P1-6）

- 被编辑的条件行加一次性高亮：`@keyframes row-flash { from { background:#eef5fd; } to { background:transparent; } }`，600ms，`animation-fill-mode: forwards`；由 `ClauseEditor` 的 `patch()`（[ClauseSummary.tsx:17](../../tagpilot-assistant/src/ClauseSummary.tsx:17)）触发本地 `dirtyFlash`，而不是每次渲染都播。
- "改/新"角标从 11px 提到 12px，加 1px 边框（`border:1px solid #c9dcf0`），与"待确认/待补充"角标同层级。
- 人数区：数字 ⟷ "—" 用 120ms 透明度交叉淡化，并在下方加一行 11px 的"人数已失效，修改后需重新统计"（语义已有，只是视觉未强调）；状态胶囊切换到"未保存"时加 400ms 的底色脉冲（`#fff7e8 → var(--soft)`），只播一次。

### 4.7 图表入场与拖拽重绘（解决 P1-5）

- **不要**再给 canvas 叠加第二个 ECharts 动画；把入场放在图表区块外层：`.insight-chart { animation: chart-in 200ms var(--ease-standard) both; }`，`@keyframes chart-in { from { opacity:0; transform:translateY(6px);} }`，同屏多图用 `--i` 索引做 40ms×最多 3 的错峰。KPI 数字与表格套同一条，保持"整块出现"。
- ECharts 自身从 `animationDuration: 180` 提到 `240`、`animationEasing: "cubicOut"`，与外层 200ms 淡入基本同步；`prefers-reduced-motion` 已由 `media.matches` 关掉。
- 拖拽重绘：`ResizeObserver` 回调里 debounce 100ms；若 `document.body.classList.contains("split-resizing")`，只 `chart.resize()`，不 `setOption`；拖拽结束后再执行一次 `update()` 并把 `animation` 置为 `false`（或沿用当前 `reducedMotion` 分支），避免每帧重播。
- 导出（P2-7）：`exporting` 时按钮文案改"导出中…"，`aria-busy`；SVG/PNG 两个按钮同时禁用。

### 4.8 空状态与报告层次（解决 P1-8、P1-9、P1-12、P2-6）

- 空状态：垂直居中（`min-height: 260px; display:grid; place-content:center; text-align:center`），按钮用 `.primary`，下方补一行 12px 次说明"或直接在对话里描述想分析的维度"。运行中显示"正在生成洞察…"。
- 右栏底色从 `#fcfcfd` 提到 `#f8f9fb`（`--surface-panel`），或在保持 `#fcfcfd` 的前提下给报告区块加白底卡片；二者取其一，避免"近白叠近白"。
- 报告分区：`insight-findings`、`insight-feedback` 改为白底 `1px solid var(--border)` + 8px 圆角 + 16px 内边距（`elevation-1` 仅在 focus/悬浮时出现）；叙述段落保持无卡片。
- 吸顶：报告内的 `.insight-skill-header`（以及报告 h1）用 `position:sticky; top:0; background: color-mix(in srgb, var(--surface-panel) 92%, transparent); backdrop-filter: blur(6px);`，滚动后加 `elevation-1`（可用 `animation-timeline: scroll()` 渐进增强，或 JS 滚动阈值 8px）。顶部 tab 区本身在滚动容器之外，无需 sticky。
- 反馈：把 1–5 分下拉换成 👍/👎 两个 32×32 图标按钮（`aria-pressed`，hover 底色、按下 1px），点击即提交 `rating=5/1`；下方"补充说明"折叠展开（4.5 的 `.collapse`，160ms），提示"已记录，可补充说明"。表单整体加边框卡片，置于报告分段结尾而不是全页最底。

### 4.9 分隔手柄拖拽反馈（解决 P1-10）

- `SplitHandle` 增加本地 `dragging` 状态，透出 `data-dragging="true"` 与 `data-width`：

```css
.split-handle[data-dragging="true"]::before { background: var(--accent); width: 3px; left: 3px; }
.split-handle[data-dragging="true"] .split-handle-grip { opacity: 1; }
.split-handle[data-dragging="true"]::after {
  content: attr(data-width);
  position: absolute; top: 12px; left: 12px;
  padding: 2px 6px; border-radius: 4px;
  background: #263345; color: #fff; font-size: 11px;
  font-variant-numeric: tabular-nums;
  box-shadow: var(--elevation-1);
  pointer-events: none;
}
```

- 读数出现无进场动画，松开后 120ms 淡出；`prefers-reduced-motion` 下去掉淡出，直接隐藏。键盘方向键调整时同样短暂显示 800ms。

### 4.10 可访问性核对

- 新增动画全部加入 reduced-motion 关闭清单。注意现有全局规则只关 `transition`（[index.css:1477-1482](../../tagpilot-assistant/src/index.css:1477)），新增的 `animation`（spinner 除外，它表达"进行中"且应保留）必须逐个声明 `animation:none`。
- focus-visible 已由全局 2px accent + 3px offset 覆盖（[index.css:50-57](../../tagpilot-assistant/src/index.css:50)）；按下态与 loading 不得移除 outline。
- 右栏 tab 建议顺手换成 `role="tablist"` + `role="tab"` + `aria-selected`，与移动端 [App.tsx:917-940](../../tagpilot-assistant/src/App.tsx:917) 统一，并补左右方向键切换。
- `plan-status`、`notice` 已有 `role="status"`；新增的加载文案沿用即可。

## 5. 与整体设计语言的关系

右栏的扁平不是"缺少阴影"，而是 DESIGN.md 只写了静态颜色、没有写瞬时状态：默认/悬停/选中都有定义，按下、等待、折叠、拖拽中却全部留空，组件只能退化为"变色即反馈"。建议把本文的 pressed / pending / transition / elevation 作为一组**状态层 token** 补进 DESIGN.md，并明确"投影仅用于瞬态浮层、位移仅用于按下 1px 与面板进出"；这样既保留白灰平面的一面，也不违背现有的 reduced-motion、focus 可见与"状态可读"三条约定。
