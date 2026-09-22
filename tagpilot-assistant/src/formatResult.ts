import type { RetrieveResult } from "./api";

export const DECISION_TEXT: Record<string, string> = {
  CANDIDATES_ONLY: "已找到候选标签，请核对业务口径。",
  NEEDS_CONFIRMATION: "DSL 已通过门禁，请确认后再交给客群执行服务。",
  NEEDS_VALUE: "已唯一识别标签，但仍需补充条件值并确认。",
  CLARIFY: "查询条件需要补充时间范围或明确业务口径，请修改后重试。",
  INEXPRESSIBLE: "现有码值分档无法精确表达该条件，请调整条件或选择连续数值标签。",
  REJECTED_BY_DSL_GATE: "大模型建议未通过 DSL 门禁，已阻止执行。",
};

export type MessageLike = {
  role?: string;
  content?: unknown;
};

export function lastUserText(messages: readonly MessageLike[]): string {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role !== "user") continue;
    const content = message.content;
    if (typeof content === "string") {
      return content.trim();
    }
    if (!Array.isArray(content)) continue;
    const text = content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "type" in part && (part as { type?: string }).type === "text") {
          return String((part as { text?: string }).text || "");
        }
        return "";
      })
      .join("\n")
      .trim();
    if (text) return text;
  }
  return "";
}

export function formatRetrieveText(result: RetrieveResult): string {
  const decision = result.decision || "";
  const lines = [
    DECISION_TEXT[decision] || "请核对候选标签的业务口径。",
    "",
    `决策：${decision || "-"}`,
    `快照：${result.snapshot_id || "-"} · 构建：${result.build_id || "-"}`,
    `选择器：${result.selector || "-"} · 大模型已连接：${result.model_connected ? "是" : "否（精确证据演示模式）"} · DSL：${result.dsl_valid ? "合法，待确认" : "尚未生成"}`,
  ];
  if (result.explanation) {
    lines.push(`说明：${result.explanation}`);
  }
  if (result.validation_error) {
    lines.push(`门禁：${result.validation_error}`);
  }
  const candidates = result.candidates || [];
  if (candidates.length === 0) {
    lines.push("", "当前可用范围内没有候选标签。");
    return lines.join("\n");
  }
  lines.push("", "候选标签：");
  candidates.forEach((item, index) => {
    lines.push(`${index + 1}. ${item.name || "-"} · 标签族 ${item.family_key || "-"} · 码值 ${item.code || "-"}`);
  });
  lines.push("", "结果必须由你确认，不会自动执行客群筛选。可在下方候选卡片点「符合需求」记录反馈。");
  return lines.join("\n");
}
