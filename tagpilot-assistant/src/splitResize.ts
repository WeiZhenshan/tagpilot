export type SplitSide = "left" | "right";
export type RightPanelMode = "plan" | "insight";
export type SplitWidths = { left?: number; plan?: number; insight?: number };

export const SPLIT_LIMITS = {
  left: { min: 176, max: 420 },
  right: { min: 300, max: 720 },
  center: 340,
  handle: 9,
} as const;

const STORAGE_KEY = "tagpilot:split-widths";

type ClampInput = { total: number; other: number; handles: number };

export function clampSplitWidth(side: SplitSide, width: number, { total, other, handles }: ClampInput): number {
  const limits = side === "left" ? SPLIT_LIMITS.left : SPLIT_LIMITS.right;
  const available = total - other - handles * SPLIT_LIMITS.handle - SPLIT_LIMITS.center;
  const upper = Math.max(limits.min, Math.min(limits.max, available));
  return Math.round(Math.min(Math.max(width, limits.min), upper));
}

function readWidth(value: unknown, limits: { min: number; max: number }): number | undefined {
  if (typeof value !== "number" || !Number.isFinite(value)) return undefined;
  return Math.round(Math.min(Math.max(value, limits.min), limits.max));
}

export function readSplitWidths(storage: Pick<Storage, "getItem">): SplitWidths {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      left: readWidth(parsed.left, SPLIT_LIMITS.left),
      plan: readWidth(parsed.plan, SPLIT_LIMITS.right),
      insight: readWidth(parsed.insight, SPLIT_LIMITS.right),
    };
  } catch {
    return {};
  }
}

export function writeSplitWidths(storage: Pick<Storage, "setItem">, widths: SplitWidths): void {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(widths));
  } catch {
    /* 存储不可用时仅本次会话生效。 */
  }
}
