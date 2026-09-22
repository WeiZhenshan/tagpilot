---
name: TagPilot Assistant 圈选工作台
description: 以对话核对业务口径、编辑条件并明确确认创建的简洁白灰工作台
colors:
  primary: "#409eff"
  primary-action: "color-mix(in srgb, var(--accent) 60%, #000)"
  primary-action-hover: "color-mix(in srgb, var(--accent) 50%, #000)"
  paper: "#fff"
  soft: "#f6f7f9"
  panel: "#fcfcfd"
  ink: "#24272c"
  muted: "#68717d"
  border: "#e7e9ed"
  input-border: "#d9dde3"
  hover: "#f0f2f5"
  selected: "#e8ecf2"
  selected-ink: "#17243a"
  send: "#263345"
  send-hover: "#37465b"
  disabled-ink: "#959ba4"
  disabled-bg: "#f5f6f8"
  danger: "#b42318"
  danger-bg: "#fff4f2"
  warning: "#845714"
  warning-bg: "#fff7e8"
  bound: "#347451"
  pending: "#9a6700"
  choice-ink: "#235382"
  choice-border: "#79a4cc"
  choice-bg: "#f0f6fb"
typography:
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "14px"
    lineHeight: 1.85
  title:
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.6
  control:
    fontSize: "13px"
    lineHeight: 1.6
  label:
    fontSize: "12px"
    lineHeight: 1.6
  metadata:
    fontSize: "11px"
    lineHeight: 1.6
  count:
    fontSize: "23px"
    fontWeight: 600
    lineHeight: 1.6
rounded:
  control: "6px"
  card: "8px"
  conversation: "10px"
spacing:
  compact: "6px"
  field-gap: "8px"
  control-gap: "10px"
  small: "12px"
  medium: "16px"
  panel: "18px"
  large: "20px"
  spacious: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary-action}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
    typography: "{typography.control}"
  button-primary-hover:
    backgroundColor: "{colors.primary-action-hover}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
    typography: "{typography.control}"
  button-send:
    backgroundColor: "{colors.send}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "5px 14px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    padding: "2px 4px"
    typography: "{typography.label}"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
    typography: "{typography.control}"
  history-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.selected-ink}"
    padding: "10px"
    rounded: "{rounded.control}"
  ask-card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.card}"
    padding: "16px"
  choice-selected:
    backgroundColor: "{colors.choice-bg}"
    textColor: "{colors.choice-ink}"
    rounded: "{rounded.control}"
    padding: "7px 12px"
---

# Design System: TagPilot Assistant 圈选工作台

## Overview

**Creative North Star: "简洁白灰圈选工作台"**

本文仅约束 `tagpilot-assistant` 模块，依据本模块当前 CSS 和 React 实现记录，不覆盖若依其他页面、Element UI 组件或全仓库设计规则。用户已指定 assistant-ui 简洁白灰方向并允许直接完成实现；本次没有独立概念轮或生成图。

界面服务于企业后台中的客户圈选操作：对话承接意图，条件方案持续可核对，关键状态与权限通过文字和控件可用性表达。白色内容面、浅灰分区、细边框建立层次；强调色沿用宿主主题，字体沿用中文系统字体栈。

**Key Characteristics:**

- 白灰底色、细线分区、低装饰密度。
- 对话与可编辑条件并列，依据与技术详情按需展开。
- 状态文字、明确确认、历史版本与当前结果相互对应。
- 窄屏提供历史、对话、圈选方案三个分区入口。

来源为仓库 `PRODUCT.md`、`docs/development/Agent-V2界面方向.md` 及本模块 `src/index.css`、`src/App.tsx`、`src/PlanPanel.tsx`、`src/AgentConversation.tsx`。token 以前置 YAML 为准；侧车记录焦点、动态与断点等扩展，不建立第二份基础 token。

审查边界：本次文档核对为源码提取。原始独立审查读取三张真实 DOM、合成测试数据截图（1440×960 桌面 Ask、桌面方案，以及 390×844 移动方案）及组件源码，结论为 fix。五项问题为窄屏错误横幅隐藏、蓝底白字对比度、样例弹窗键盘行为、移动历史缺失与 Tab 截图不一致、测试数据 Invalid Date。修复复审逐项判定 resolved，disposition 为 ship；仅覆盖该清单，不代表所有业务、所有页面、全部主题组合或完整可访问性认证。合成数据只用于界面状态测试，不构成真实模型效果或银行业务验收。本次没有独立 QUALITY BAR 或概念轮，不将用户指定方向后的直接实现描述为已完成这些流程。

## Colors

### Primary

主题蓝使用 `primary`，运行时由宿主同源主题消息更新 `--accent`。它承担焦点、光标与主按钮边框；操作按钮背景使用 `primary-action` 深色混合，悬停进一步加深，避免直接将明亮主题色用于白字按钮。发送与停止按钮使用独立的深灰蓝 `send`。

### Neutral

`paper` 为对话和输入面；`soft` 为历史栏；`panel` 为方案栏；`border` 为分区和控件细线。`ink`、`muted` 区分正文与辅助信息，选中历史项由 `selected` 和 `selected-ink` 表达。

错误使用 `danger` 与浅红底，待处理警告使用 `warning` 与浅黄底，已匹配状态使用 `bound`，待补充状态使用 `pending`。选项按钮使用低饱和蓝色选中面。状态同时保留可读文字。

**The 状态可读 Rule.** 颜色与文字共同表达状态；不得只靠圆点颜色区分已完成、待完成或错误。

## Typography

正文与控件共用前置 token 的系统中文字体栈；不下载字体。行高继承基础值（1.6），消息正文使用 `body` 的宽松行距，欢迎说明另用行距（1.9）。

面板标题使用 `title`，条件和表单控件使用 `control`，状态使用 `label`，时间与依据使用 `metadata`；工具事件的次要说明可到（10px）。统计人数使用 `count`，数字采用等宽数字特性 `tabular-nums`。消息最大行长（74ch），用户消息最多占可用宽度（90%）。

欢迎区现有标题为（26px / 600 / -0.5px 字距），窄布局降为（23px）。这是当前模块的局部实现事实，不作为全仓库展示字体规则，也不鼓励扩展为营销式大标题。

## Layout

桌面工作台占满父容器高度。顶部栏高（58px），左侧历史栏（224px），中间对话区弹性分配且最小宽度（340px），右侧方案栏（370px）。历史列表、对话正文与方案正文各自滚动；方案动作区保持可见，最大高度（48%）并允许内部滚动。

对话编辑器最大宽度（760px），欢迎区最大宽度（600px）；编辑器输入高度（68–180px）。布局间距以（8/12/16/20/24px）为常用节奏，方案正文内边距（18px），条件树用左边线与（10px）缩进表达层次。

| 视口条件 | 当前实现 |
| --- | --- |
| ≥1600px | 历史栏 240px，方案栏 420px |
| ≤1150px | 历史栏 175px，方案栏 330px，缩小对话与顶部内边距 |
| ≤900px | 历史栏 145px，方案栏 300px，对话最小宽度 290px，隐藏顶部辅助状态 |
| ≤760px | 顶部栏 54px；三分区 Tab 切换；对话最小宽度归零；历史或方案覆盖工作区剩余区域 |

移动历史与方案从主体内顶部偏移（103px）展开；错误横幅在这两种分区仍显示且位于面板之上。选择历史或新建任务后返回对话。实际实现为三个分区切换，与已同步的界面方向文档一致。

## Elevation & Depth

当前界面没有 `box-shadow`。层次来自背景明度、细边框与位置；样例弹窗使用半透明深色遮罩（`#1d26354d`），遮罩层级（20），移动历史层级（2）与错误提示层级（4）。不要为普通面板增加无来源的投影。

## Shapes

控件采用 `control` 圆角，处理记录与 Ask 卡采用 `card`，用户消息、编辑器与样例窗口采用 `conversation`。边框通常为（1px）；条件树保留左侧细线。回到最新消息采用局部胶囊圆角（18px），进度圆点为圆形；这些局部形态不扩展到所有按钮。

## Components

### Buttons

主按钮用于保存核验、提交回答、创建与打开客群；普通按钮承接统计、样例、取消。发送/停止共用深灰蓝样式。禁用态使用禁用文字与浅灰背景，保持 `not-allowed` 光标。默认悬停只改变背景，过渡为（0.15s），没有位移动画。

### Fields and Composer

普通输入框、选择框与文本框使用细边框与一致圆角，均保留可访问名称。控件与 `summary` 的键盘焦点为主题色（2px）外轮廓、偏移（3px）。对话输入框通过整个编辑器 `focus-within` 的边框变化表达焦点（`#8896a8`）；其输入元素覆盖默认 outline，这是当前例外，不能推广到其他输入框。

系统开启减少动态时关闭所有 transition，并把滚动行为设为 `auto`。不要为处理进度增加与实际运行无关的循环动画。

### Navigation and History

桌面历史列表有新建、当前页搜索、最近/归档切换与分页；日期按 `zh-CN` 本地显示。选中项用浅灰蓝底，长标题截断。移动端以历史、对话、圈选方案三个可聚焦按钮承接分区，使用 `tablist` / `tab` 与 `aria-selected`；不要据此宣称已覆盖全部 ARIA Tabs 方向键交互规范。

### Conversation, Process and Ask

欢迎页示例直接发起圈选；消息标明“你”或“圈选助手”。处理记录采用可折叠容器，三个步骤是否完成由意图、已匹配条件、有效方案事件决定；停止后保留已有记录。等待补充时展示 Ask 表单，选项有 `aria-pressed`，亦可手填；缺少回答或请求处理中禁用提交。失败或中断用文字解释并提供从保存位置继续。连接恢复只轮询更新，不重复提交需求。

### Plan and Results

条件树使用“全部满足/任一满足”，支持修改比较方式、码值、数值与移除条件。码值显示中文标签，单位及倍率不能隐藏；依据与技术版本使用折叠详情。历史方案只读，可作为新版本继续；编辑后明确提示旧人数失效。人数仅在统计 revision 与当前 revision 一致时展示，展示本地化统计日期时间、数据时点与警告。

执行按钮需同时满足有效方案、未修改、当前版本、非运行/等待状态及对应 capability。创建先展开名称和当前版本/条件数确认，再由“确认创建”提交。样例使用原生 `dialog.showModal()`；Escape 关闭、Tab / Shift+Tab 在弹窗焦点范围循环，关闭后返回触发控件。样例表横向滚动，空结果有文字说明；样例不写入会话或发送给模型。

## Do's and Don'ts

### Do:

- **Do** 继续使用模块白灰分区、细边框和中文系统字体，保持视觉作用域仅在本模块。
- **Do** 将人数、版本、权限与运行进度对应到实际数据，并用中文文字说明状态。
- **Do** 为新增交互保留键盘焦点、明确名称和减少动态支持。
- **Do** 在移动端保留历史、对话、方案以及错误恢复入口。

### Don't:

- **Don't** 用装饰性动效或无依据的完成状态替代真实处理反馈。
- **Don't** 隐藏条件值单位倍率，或把旧方案人数当作当前人数。
- **Don't** 把本模块的局部字体例外、断点偏移或五项复审结论提升为全项目规则或完整认证。
- **Don't** 未经用户指定把此设计推广到其他若依页面。
