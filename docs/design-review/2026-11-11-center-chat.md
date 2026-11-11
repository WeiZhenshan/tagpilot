# TagPilot 工作台 · 中间对话区交互反馈评审

- 日期：2026-11-11
- 范围：`tagpilot-assistant` 中间对话区（欢迎区、消息流、RunTimeline、Ask 卡、Composer、下拉菜单、滚动、移动端 Tab）
- 方法：源码逐状态核对（CSS + 组件逻辑），对照 `DESIGN.md` 与 `panel-motion.css` 现有动效 token；:5174 服务可访问，但本机浏览器预览不可用，未做截图，所有结论均可在所列行号复核
- 不在范围：功能正确性、右栏方案编辑器的表单细节、整体信息架构

---

## 一、现象总述

对话区的"平面感"不是某几处样式没写，而是**反馈通道被收敛到只剩"颜色"这一条**：没有阴影（`DESIGN.md:181`）、悬停只变背景 0.15s（`DESIGN.md:191`）、没有位移动画、没有任何 `:active`（全仓库 CSS 只有分隔条用了 `:active`，`src/index.css:1529`）。当按钮既不变形、也不下沉、也不出现焦点环过渡时，唯一能变化的就是一层很浅的灰（`#fff → #f0f2f5`，对比度极低），用户感知不到"按到了"。

更关键的是**发送链路本身没有中间态**：assistant-ui 在 `send()` 的第一步就把输入框清空（`node_modules/@assistant-ui/core/dist/runtime/base/base-composer-runtime-core.js:150`），而真正的用户气泡要等 `createThread` + `startRun` 两个串行请求返回后才出现（`src/App.tsx:467-483`）。于是回车后发生的是：文字消失 → 画面恢复原样 → 1~3 秒后消息"啪"地出现。这是"没有我做了操作的感觉"最直接的来源，其严重程度高于任何 CSS 细节。

已经做对、值得作为语言锚点的四处：

- 「回到最新消息」胶囊（`index.css:853-890`）：opacity 0.16s + `translate(-50%, 8px)` + `cubic-bezier(0.22,1,0.36,1)` 0.2s，出现/消失都是完整的进出场——目前对话区唯一"有质感"的反馈。
- 运行中行内的 shimmer 与 900ms 旋转指示（`index.css:1157,1176-1177`）：绑定了真实运行状态，不属于"装饰性循环动画"。
- 新事件行的 `run-enter` 160ms 淡入 + 4px 位移（`index.css:1161,1188`）。
- 输入器内引用块 `.analysis-cite` 的选中态、`focus-visible` 双层 ring（`index.css:783-796`）。

以下判断都以这四个为基准：问题不是"动效太少"，而是**同一套语言只覆盖了少数元素**。

### 状态覆盖对照

| 元素 | default | hover | focus-visible | active | selected | disabled | loading/busy |
|---|---|---|---|---|---|---|---|
| 欢迎示例按钮 | ✓ | ✓ 仅背景 | ✓ | ✗ | n/a | ✓ | ✗ |
| 发送按钮 | ✓ | ✓ 仅背景 | ✓ | ✗ | n/a | ✓ | ✗ 无任何 loading 态 |
| Composer 容器 | ✓ | n/a | ✓ 仅边框变色、无过渡 | n/a | n/a | **✗ 无禁用样式** | ✗ |
| 用户气泡 | ✓ | n/a | n/a | n/a | n/a | n/a | ✗ 无"发送中" |
| 助手消息 | ✓ | n/a | n/a | n/a | n/a | n/a | ✗ 无流式光标/占位 |
| RunTimeline 标题 | ✓ | ✓ 整行灰带 | ✓ | ✗ | n/a | n/a | ✓ 旋转 + shimmer |
| RunTimeline 条目 | ✓ | ✓ 整行灰带 | ✓ | ✗ | n/a | n/a | ✓ 仅最新行 shimmer |
| Ask 选项 | ✓ | ✓ | ✓ | ✗ | ✓ 仅色，无过渡 | ✓ | ✗ |
| Ask 提交 | ✓ | ✓ | ✓ | ✗ | n/a | ✓ | ✗ 无"提交中" |
| 下拉菜单 / 技能菜单 | ✓ | ✓ | ✓ 焦点环 | n/a | ✓ | ✓ | ✗ 无进出场 |
| 移动端 Tab | ✓ | ✓ | ✓ | ✗ | ✓ | n/a | n/a |

---

## 二、发现清单

### P0 — 用户明确感知"没反应"

#### F1 发送链路没有任何"已提交"确认
- 位置：`src/AgentConversation.tsx:189-205`（`onNew`）、`src/AgentConversation.tsx:335-340`（技能模式回车）、`src/App.tsx:424-439`（`operation`）、`src/App.tsx:467-483`（`send`）
- 现状：`onNew` 直接 `await onSend(text)`，`send` 内部先 `createThread` 再 `startRun`，两者都成功后才 `setThread`。这期间没有本地消息、没有骨架、没有 spinner、没有 `aria-busy`。
- 后果：assistant-ui 在点击/回车瞬间已清空输入框（上游 `base-composer-runtime-core.js:150`），用户看到的是"我写的字没了，界面没变"。若网络慢或后端排队，这段空白可达数秒；这正是用户描述的"点了没反应"。
- 备注：失败时会把文本写回输入框（`AgentConversation.tsx:202`），所以失败体验反而比"等待"更完整——说明只缺中间态。

#### F2 等待期间输入器被禁用，但视觉上完全看不出
- 位置：`src/AgentConversation.tsx:193-194`（`isDisabled` 含 `pending`）、`src/index.css:58-73`（只有 `input:disabled` / `select:disabled`，**没有 `textarea:disabled`**）、`src/index.css:797-808`（`.composer-input` 背景透明、无禁用态）
- 现状：`pending` 为 true 时 textarea 被真正 disabled，但颜色、背景、光标外观与可用时一致；placeholder 也不变（`AgentConversation.tsx:411-417` 只处理 `disabled` 与 `WAITING`，不处理 `pending`）。
- 后果：用户继续打字，字打不进去，没有任何解释；结合 F1，这 1~3 秒里整个输入区是"假活"的。这是比"没有动效"更严重的反馈错误——不是反馈弱，是反馈错误。

#### F3 全站按钮没有按下态
- 位置：`src/index.css:32-49`
- 现状：`button` 只声明了 `transition: background 0.15s`，`:hover` 换背景，没有 `:active`、没有 `transform`、没有 `box-shadow` 变化。全仓库唯一的 `:active` 是分隔条（`index.css:1529,1551`）。
- 后果：鼠标按下与悬停视觉完全一致，"按下去"这件事在物理上不存在。这是"任何按钮都没有操作感"的全局根因，涵盖发送、示例、Ask 选项、菜单项、运行记录标题。

#### F4 欢迎区示例是首屏唯一入口，点击后画面原样不动
- 位置：`src/AgentConversation.tsx:245-266`；样式 `src/index.css:688-704`
- 现状：示例按钮点击直接 `void onSend(s)`，走 F1 的同一条无中间态链路；按钮唯一的变化是 `pending` 期间变成 disabled 灰态。箭头 `→` 是静态的，没有位移；`border-color: #edf0f3` 悬停不变。
- 后果：新用户第一次操作（首屏最显眼的四个按钮）就是"点了没反应"，第一印象直接成立。

### P1 — 反馈弱、缺失或不一致

#### F5 消息没有入场、没有消息级操作、运行中没有占位
- 位置：`src/AgentConversation.tsx:269-290`；`src/index.css:705-736`
- 现状：`.message` 无任何 animation；用户气泡与助手消息都是瞬时出现。助手消息在 `busy` 期间没有任何"正在分析…"占位或流式光标，要等第一条快照带回文本才出现整块内容。消息上没有复制/引用/重试等悬浮操作（没有使用 assistant-ui 的 ActionBar 体系）。
- 后果：一轮对话的三个关键时刻（我发了、它在想、它说完了）没有任何一个被视觉标记；用户唯一能判断"还在跑"的地方是折叠标题里的旋转图标，离视线焦点（消息末尾）很远。

#### F6 Composer 焦点态是瞬变，且没有层次
- 位置：`src/index.css:741-750`（`.composer` / `:focus-within`）、`src/index.css:797-808`（`outline:none !important`）
- 现状：`.composer` 没有 `transition`；聚焦时边框从 `#d9dfe7` 瞬间变为 `#8896a8`，没有 ring、没有阴影。textarea 的默认 outline 被强制去掉，整个输入区唯一可聚焦线索就是这条颜色很接近的细边框。
- 后果：点击输入框是本工作台最高频的操作，它却是"瞬间跳一下"的；同时输入器与聊天背景同为白色，无阴影、无底色差，视觉上不像一个可以操作的控件（见 F17）。

#### F7 发送 ↔ 停止是换节点，宽度和标签跳变，且两者同色
- 位置：`src/AgentConversation.tsx:429-449`；`src/index.css:838-846`
- 现状：`busy(thread)` 时渲染 `ComposerPrimitive.Cancel`，否则渲染 `ComposerPrimitive.Send`，同一位置替换 DOM 节点；按钮宽度随"发送 / 停止处理"文字长度变化，`margin-left:auto` 导致左边缘跳动；两者共用深灰蓝 `#263345`，停止没有危险色或意象区分。
- 后果：运行开始时右下角按钮"闪"一下变宽变字；更实际的是，深色停止按钮容易误触，而它恰好出现在模型刚开始跑的时候。

#### F8 RunTimeline 展开/收起无过渡，且完成瞬间自动折叠
- 位置：`src/RunTimeline.tsx:67-69`（`open` 初始与 effect）、`src/RunTimeline.tsx:98-107`（条件渲染内容）；`src/index.css:1141-1143`
- 现状：只有 chevron 有 `transform 160ms`；`run-content` 是 `open ? <div> : null`，出现/消失是布局瞬间切换。`useEffect(() => setOpen(running || waiting), [runId, running, waiting])` 使运行结束的那一刻整个执行记录自动收起。
- 后果：这正是用户最想回看的时刻（刚跑完），内容却一次性消失，只剩标题；chevron 在转、内容在跳，同一组件内两种节奏。
- 对照：`.run-entry` 的 160ms 入场动画（`index.css:1161`）是对的，但它只作用于新增条目，救不了容器本身的硬切。

#### F9 事件节流节奏与快照节奏脱钩，结束时会一次性"倾倒"
- 位置：`src/useEventPacer.ts:16-34`（固定 180ms/条）、`src/useEventPacer.ts:36-51`（narration 2 字符/32ms）；快照轮询 `src/App.tsx:354-382`（忙时 1s 一次）
- 现状：事件以每 180ms 一条匀速放出，但数据源是每 1s 一整份 `Thread` 快照。一次快照带来 6 条事件时，界面要播 1.08 秒，下一次快照又到了，于是形成"一阵一阵"的播放；当 `running` 变为 false，pacer 直接把 `count` 拉到 `events.length`（`useEventPacer.ts:25`），剩余事件瞬间全部出现，紧接着 F8 的自动折叠。
- 后果：用户感知为"卡顿—爆发—消失"，与"模型在持续工作"的真实过程不符；运行中最需要连续性的时间轴反而是全屏最不连续的元素。narration 打字（约 62 字符/秒）与事件 180ms 节奏也没有任何关联，长句还没打完，下一条事件已经顶上来。

#### F10 步骤状态是瞬时换图，没有"完成"这一下
- 位置：`src/RunTimeline.tsx:7-12`、`src/index.css:1154-1159`
- 现状：`StatusIcon` 在 `active / done / blocked` 之间切换的是不同 DOM（spinner 圆环 → 对勾 SVG），没有过渡、没有缩放、没有颜色渐变。`marker-done` 只是换 `color`。
- 后果：4 个阶段、每个阶段若干条操作的完成，全部是"无声切换"；旋转圆环停转、对勾出现，这是最应该给"叮"一下的位置。

#### F11 Ask 卡：选中只是一层淡蓝，提交后不锁定、直接消失
- 位置：`src/AgentConversation.tsx:36-92`（Ask 表单）、`src/AgentConversation.tsx:79-89`（提交/停止）；`src/index.css:1199-1238`
- 现状：选项是普通按钮 + `aria-pressed`，`[aria-pressed="true"]` 只改三个颜色属性（`index.css:1223-1227`），全局过渡只有 `background`，边框与文字颜色是瞬变；没有勾选标记。提交后 `pending` 只禁用"提交并继续"和"停止处理"，**选项按钮与文本输入仍可点击/编辑**，用户会以为还能改；卡片在状态转为 RUNNING 后直接卸载，无退场。
- 后果：Ask 卡是全流程里唯一需要用户做决策的地方，反馈强度却低于普通下拉菜单。

#### F12 菜单瞬间出现，且两个菜单的层次语言不一致
- 位置：`src/ListboxSelect.tsx:200-237`（`open ? <div> : null`）；`src/index.css:153-167`（`.library-options` 有 `0 8px 24px rgba(38,51,69,.12)`）、`src/index.css:941-944`（`.plan-menu-options` 无阴影）；`src/insight/workbench-insight.css:42-54`（`.skill-menu` 无阴影、无动画）
- 现状：三类浮层（列表选择、方案更多操作、"/"技能菜单）都是条件渲染瞬时出现/消失，没有 `@starting-style`、没有位移或缩放。同为浮层，只有 `.library-options` 有投影，另外两类只有 1px 边框。
- 后果：打开菜单时没有任何"它从触发点长出来"的空间关系；层次靠边框，和白底页面几乎糊在一起。技能菜单从输入框上方突然出现一大块 300px 高面板，尤其突兀。

#### F13 图表点选在图内没有反馈，确认条出现在图表下方
- 位置：`src/insight/InsightChart.tsx:73-74`（ECharts click 直接回调）、`src/insight/AnalysisMessageParts.tsx:44-48`（选中条）、`src/insight/analysis-message.css:11`
- 现状：点击柱子/扇区时，图表本身不进入任何 selected/highlight 状态，也不改变指针光标；界面唯一的响应是工具栏下方插入一条灰底"已选择：X"（`analysis-message.css:11`）。图表画布高 330px，确认条很可能在视口外。
- 后果：用户点了一下柱子，眼睛盯着柱子——柱子没变。这是对话内嵌卡片里最典型的"点了没反应"。

#### F14 移动端 Tab 切换是瞬时重绘
- 位置：`src/App.tsx:917-940`（tablist）；`src/index.css:1427-1439`（Tab 样式）、`src/index.css:1440-1456`（面板 `display` 切换）
- 现状：选中态只是背景色（有 0.15s 背景过渡），面板通过在 `mobile-chat / mobile-plan / mobile-history` 之间切换 `display` 来替换，没有任何过渡。
- 后果：底部三大区切换像刷新页面；没有方向感，用户不知道"新面板从哪边来"。

#### F15 "方案变更"跳转看不到变化
- 位置：`src/RunTimeline.tsx:45-48`（点击"方案变更 · N 项"）、`src/App.tsx:996-1000`（`onReveal`）、`src/ClauseSummary.tsx:75`（`data-highlighted`）、`src/index.css:1505`（outline 高亮）
- 现状：点击后打开右栏并聚焦编辑器，但**不会把高亮条件滚动到可视区**；高亮用 1px outline 表示且没有过渡；`highlightedClauses` 设置后没有任何清除逻辑（`App.tsx:67` 只有 setter 调用点，无清空），会一直留着。
- 后果：右栏已经打开、或高亮条件在滚动区之外时，点击"方案变更"后视觉上什么都没发生；高亮长期驻留又会让下一次点击失去区分度。这是对话区发出的跨栏动作里唯一"无结果"的一个。

#### F16 横幅、降级、错误块瞬时插入，整段内容位移
- 位置：`src/AgentConversation.tsx:293-312`；`src/App.tsx:941-953`；`src/index.css:1083-1090`（`.run-degraded`）、`src/index.css:1239-1248`（`.run-error`）、`src/index.css:1249-1262`（`.banner`）
- 现状：三类状态块都是条件渲染，出现/消失无过渡；`.banner` 插在标题与消息流之间，出现时把整个消息流向下推约 38px；错误消失时又"弹"回去。
- 后果：错误提示本应被注意到，这种硬插入造成的是布局抖动而非注意力引导。

### P2 — 细节

#### F17 输入器与聊天区没有层次差
- 位置：`src/index.css:737-747`
- 现状：`.composer` 白底、1px `#d9dfe7` 边框、无阴影；聊天区同样白底。全站仅有 3 处 `box-shadow`（`index.css:166,795,867`），输入器不在其中。
- 建议：输入器是"可操作物体"，应该拥有全站最稳定的 `shadow-1`，而不是和其他白面共面。

#### F18 输入器高度变化与附属行插入是瞬时的
- 位置：`src/index.css:797-808`（`min-height:68px; max-height:180px`）；`src/AgentConversation.tsx:341-343`（技能 chip 行）、`src/AgentConversation.tsx:344-372`（引用块）、`src/insight/workbench-insight.css:55`（`.skill-selection`）
- 现状：assistant-ui 使用 `react-textarea-autosize`，高度按行像素级即时设置；技能 chip 行、引用块都是在编辑器上方整行插入，`.composer` 高度瞬时增加 30~70px，整个消息区跟着跳。
- 说明：**不要**给真正的逐行增高加 transition（会和输入争夺每一次按键）；要处理的是"整块附属行插入/移除"这一类离散高度变化。

#### F19 选中态与悬停态同色
- 位置：`src/index.css:183-190`（`.library-option` hover 与 `[aria-selected]` 同为 `#eef2f7`）；`src/insight/workbench-insight.css:47`（技能菜单 option 同理）
- 现状：菜单里鼠标悬停项与当前选中项背景一致，只能靠勾选图标和 500 字重区分。
- 建议：选中用 `--selected:#e8ecf2`（DESIGN 既有 token），悬停用 `#f0f2f5`，二者分离。

#### F20 自动跟随滚动是硬跳
- 位置：`src/AgentConversation.tsx:170-188`
- 现状：`element.scrollTop = element.scrollHeight`，在每条历史/新事件挂载时（ResizeObserver）瞬时对齐；pacer 每 180ms 追加一条，等于每 180ms 一次小跳。
- 说明：流式追加时**不应**使用平滑滚动（会互相打断、拖尾），但可以用 rAF 合并、并只在到达新内容前留出 8~12px 呼吸区；真正的平滑只留给"回到最新消息"按钮（已实现）。

#### F21 运行记录标题的 hover 是整行灰带，与卡片圆角语言冲突
- 位置：`src/index.css:42-44`（全局 `button:hover`）与 `src/index.css:1136-1140`
- 现状：`.run-heading` / `.run-entry-toggle` 自身声明 `background: transparent`，但全局 `button:hover:not(:disabled)` 的特异性更高（0,2,1 > 0,1,0），于是整行 760px 宽的直角灰带出现；同文件里 `.run-heading:hover { color: var(--ink) }` 又是无效声明（颜色本来就是 ink）。
- 后果：一个轻量标题变成了表格行高亮，反馈强度与元素权重不匹配。

---

## 三、对话区交互反馈优化建议

### 3.1 先补一套动效 token（`index.css :root` 或新建 `motion.css`）

```css
:root {
  --motion-press: 80ms;
  --motion-fast: 120ms;
  --motion-base: 160ms;
  --motion-slow: 220ms;
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
  --ease-enter: cubic-bezier(0.16, 1, 0.3, 1);   /* 复用 panel-motion 的进入曲线 */
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);

  /* 阴影只给"浮起来的东西"三层，不进入普通面板 */
  --shadow-1: 0 1px 2px rgb(38 51 69 / 6%);
  --shadow-2: 0 8px 24px rgb(38 51 69 / 12%);    /* 已是 .library-options 现值 */
  --shadow-3: 0 16px 40px rgb(38 51 69 / 16%);
  --ring-focus: 0 0 0 3px rgb(64 158 255 / 14%);
}
```

规则：`--shadow-1` 只给 Composer；`--shadow-2` 给下拉/技能/更多操作菜单与 Ask 卡；`--shadow-3` 给模态/抽屉。正文面板、消息、时间轴继续无阴影。

### 3.2 发送链路（对应 F1、F2、F4）

1. **乐观气泡**：在 `AgentConversation` 内维护 `sending` 状态（`{ id, text }`），`onNew` 的最前面 set、`finally` 清；在 `ThreadPrimitive.Messages` 之前渲染一条幽灵气泡：

```tsx
{sending && (
  <div className="message user-message is-pending" aria-busy="true">
    <span className="speaker">你 · 发送中</span>
    <div className="message-text">{sending.text}</div>
  </div>
)}
```

```css
.message.is-pending { opacity: .72; }
.message.is-pending .speaker { color: var(--accent); }
```

成功时幽灵气泡与真实消息位置重合，直接移除幽灵即可；失败时幽灵淡出 120ms、文本回填输入框（现有逻辑 `AgentConversation.tsx:202` 已做回填）。

2. **Composer busy 态**：给 `.composer` 加 `:has(.composer-input:disabled)` 样式，并把 `composer-hint`（`AgentConversation.tsx:425-427`）在 `pending` 时改为"正在发送…"：

```css
.composer:has(.composer-input:disabled) { background: #fafbfc; }
.composer-input:disabled { color: #737d89; -webkit-text-fill-color: #737d89; opacity: 1; }
```

不要用整块 opacity——输入框里可能有用户要保留的内容。

3. **示例按钮点击**：点击后立刻给被点项加 `data-clicked`：箭头换成 14px 旋转圈、其余三项降到 `opacity:.5`，120ms 过渡；同时触发上面的幽灵气泡。这样"我点了第一个"在 100ms 内就有确认。

### 3.3 全局按下态（F3）

```css
button:not(:disabled) {
  transition: background var(--motion-base) var(--ease-out),
              border-color var(--motion-base) var(--ease-out),
              color var(--motion-base) var(--ease-out),
              box-shadow var(--motion-fast) var(--ease-out),
              transform var(--motion-press) var(--ease-out);
}
button:not(:disabled):active { transform: translateY(1px) scale(.98); }
```

例外：
- 整行元素（`.run-heading`、`.run-entry-toggle`、`.history-select`、`.library-option`）只做 `translateY(1px)`，不缩放，并补 `border-radius: 6px` + `background: #f0f2f5` 的局部 hover，覆盖全局 hover 的直角灰带（修 F21）。
- `.split-handle` 保持现有行为。
- `prefers-reduced-motion` 下 `transform` 归零（现有全局规则 `index.css:1477-1482` 已会关掉 transition，transform 需单独加 `transform:none !important`）。

### 3.4 Composer（F6、F7、F17、F18）

```css
.composer {
  box-shadow: var(--shadow-1);
  transition: border-color var(--motion-base) var(--ease-out),
              box-shadow var(--motion-base) var(--ease-out);
}
.composer:focus-within {
  border-color: #8896a8;
  box-shadow: var(--ring-focus), var(--shadow-1);
}
```

- 发送按钮固定 `min-width: 76px; justify-content:center`，避免"发送/停止处理"切换时左边缘跳动。
- 停止按钮改用"白底 + 危险色文字/描边"（`border-color:#d9dde3; background:#fff; color:var(--danger)`），并加方形 stop 图标，与发送按钮形成明确的语义差。
- 技能 chip 行、引用块这类离散插入用高度过渡包裹：外层 `display:grid; grid-template-rows: 0fr → 1fr; transition: grid-template-rows 200ms var(--ease-out); overflow:hidden`。不要给 textarea 的逐行增高加 transition。

### 3.5 消息流（F5、F16）

```css
.conversation-turn { animation: turn-in 180ms var(--ease-out) both; }
@keyframes turn-in { from { opacity: 0; transform: translateY(6px); } }
```

- 只作用于挂载，不作用于轮询更新——`conversation-turn` 以 `message.id` 稳定复用，文本增长不会重放动画；需要在流式文本更新时确认 React 不会 remount（当前 `ThreadPrimitive.Messages` 按 id 复用）。
- 助手消息在 `busy` 且尚无文本时，渲染一个 3 点呼吸占位（1.2s 循环，`prefers-reduced-motion` 下换成静态"正在处理…"文字）。这属于"与真实运行状态绑定"的动画，不违反 `DESIGN.md:197`。
- 消息悬浮操作：复用 `.analysis-chart-toolbar` 的下划线文字按钮语言，在 `.message:hover/:focus-within` 时在 speaker 行右侧出现「复制」「引用到输入框」；这两项不需要浮层，避免再引入一种菜单形态。
- 状态块（banner / degraded / error）用 `grid-template-rows` 展开 180ms + 内容 120ms 淡入，避免整段消息位移；`role="alert"` 保留。

### 3.6 RunTimeline 与节流（F8、F9、F10、F20）

1. **折叠过渡**：`.run-content` 外包一层 `grid-template-rows` 过渡（200ms `--ease-out`），展开时内容先于 chevron 完成；chevron 160ms 保持。
2. **不要立刻自动折叠**：`running → false` 时延迟 800ms 再收起，或在收起前把标题短暂高亮（`background:#f6f7f9` 160ms）作为"跑完了"的信号。
3. **节流改为追赶式**：

```ts
// 目标：新快照到达后 600ms 内追平，而不是固定 180ms/条
const backlog = events.length - count;
const step = Math.max(40, Math.min(180, Math.round(600 / Math.max(1, backlog))));
```

`running` 变 false 后继续按 40ms 排空尾部，而不是一次性 `setCount(events.length)`；完成后再触发第 2 条的延迟收起。
4. **narration 节奏联动**：把打字间隔从固定 32ms 改为 `clamp(12, 600 / text.length, 32)`，让一段叙述在 600ms 内讲完，与追赶节奏一致；`.run-caret` 加 1s 步进闪烁（`steps(1)`，仅在 `streaming` 时）。
5. **状态机过渡**：`marker-active → marker-done` 时对勾做 180ms `scale(.6)→1` + `color 160ms`；`blocked` 用 160ms 变色，不弹跳（避免在错误路径上做庆祝动作）。

### 3.7 Ask 卡（F11）

- 选项选中：`transition: background 120ms, border-color 120ms, color 120ms`，并在左侧用 `::before` 显示 12px 对勾（120ms 缩放进入）；选中项与 hover 项的颜色要分开（`#f0f6fb` vs `#fafbfc`）。
- 提交后整卡 `aria-busy="true"`：`opacity:.6; pointer-events:none`，提交按钮文案改"提交中…"，选项与输入框一起锁住（当前只锁了提交按钮）。
- 退场：状态离开 WAITING 后先 `data-leaving` 120ms 淡出+`translateY(-4px)`，再卸载；不要和 F8 的折叠同时发生（先让 Ask 退场，再收起时间轴 200ms）。

### 3.8 菜单与浮层（F12、F19）

```css
.library-options, .plan-menu-options, .skill-menu {
  box-shadow: var(--shadow-2);
  transform-origin: var(--menu-origin, top);
  transition: opacity 140ms var(--ease-out), transform 140ms var(--ease-out);
}
@starting-style {
  .library-options { opacity: 0; transform: translateY(-4px) scale(.98); }
  .library-options--up,
  .composer-context .library-options,
  .skill-selection .library-options { transform: translateY(4px) scale(.98); }
}
```

- `.plan-menu-options`、`.skill-menu` 补 `--shadow-2`，与 `.library-options` 对齐。
- 选中态 `background: var(--selected)` + 左缘 2px accent 条；hover 仍 `#f0f2f5`。
- 键盘高亮（`optionRefs.focus()`）保留现有 `button:focus-visible` 外轮廓，但把 `outline-offset` 从 3px 收到 0，避免 5px 菜单 padding 内被裁切。

### 3.9 图表选择（F13）

- 点击后立刻 `chart.dispatchAction({ type:"highlight", seriesIndex:0, name })` 或设置 `selectedMode:"single"`，并给画布加 `box-shadow: var(--ring-focus)` 160ms；ECharts 实例的 pointer 改为 `cursor:pointer`。
- “已选择”条插入后 `scrollIntoView({ block:"nearest", behavior:"smooth" })`（尊重 reduced motion），确保确认条出现在视野内。

### 3.10 滚动（F20）

- 自动跟随改为 rAF 合并一次每帧，保持 instant（不要 smooth）；
- 当跟随中但视口距离底部超过 240px 时（例如图表懒加载），改用 smooth 300ms；
- 「回到最新消息」胶囊保持现状，它是本区最成熟的反馈，作为其他组件的参照。

### 3.11 移动端 Tab（F14）

- Tab 选中指示用一条 2px accent 下划线，`transform: translateX(var(--tab-index))`，180ms `--ease-out`；
- 面板切换在 `@starting-style` 下做 120ms 淡入（可选 4px 位移），`display` 切换用 `transition-behavior: allow-discrete`（与 `panel-motion.css` 同一套 `@supports` 写法）。

### 3.12 实施顺序建议

| 批次 | 内容 | 理由 |
|---|---|---|
| 1 | F1/F2/F4 乐观气泡 + 发送中态 + composer 禁用视觉 | 直接消除"没反应"，改动集中在 `AgentConversation` 一处 |
| 2 | F3 全局按下态 + F6 输入器焦点/阴影 + F21 hover 收敛 | 影响面最大、纯 CSS、风险低 |
| 3 | F8/F9 时间轴过渡与追赶节奏 | 运行中最长的一段时间可见，收益最直观 |
| 4 | F5 消息入场 + F11 Ask 卡 + F12 菜单浮层 | 逐个组件补齐 |
| 5 | F13/F14/F15/F16/F18/F20 | 细节与跨栏联动 |

---

## 四、与整体设计语言的关系

扁平感的根源不是缺少花哨动效，而是 `DESIGN.md` 把"无阴影、无位移、悬停只变色"从**默认态规范**错当成了**全部状态规范**——它约束了静止与悬停，却没有约束按下、提交、加载、完成这四类"用户正在改变状态"的瞬间，结果所有反馈都被压进了一层浅灰。

建议把这条边界写回文档：**静止与常规悬停保持扁平；只有"用户操作后 ≤1s 内发生的变化"（按下、焦点、提交、状态流转、浮层出现）允许 ≤220ms 的位移/阴影/颜色过渡，以及三层有限阴影（输入器、浮层、模态）。** 这样既保留白灰工作台的克制，也能让每一次点击都留下可感知的痕迹；同时应顺带修正 `DESIGN.md:181` "当前界面没有 box-shadow"——`index.css:166` 与 `index.css:867` 其实已经用了阴影，文档与实际已经不一致。
