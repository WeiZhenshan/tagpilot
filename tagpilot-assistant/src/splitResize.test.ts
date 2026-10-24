import { describe, expect, it } from "vitest";
import { SPLIT_LIMITS, clampSplitWidth, readSplitWidths, writeSplitWidths } from "./splitResize";

describe("split resize", () => {
  it("clamps widths to the configured range", () => {
    expect(clampSplitWidth("left", 100, { total: 1200, other: 370, handles: 2 })).toBe(SPLIT_LIMITS.left.min);
    expect(clampSplitWidth("right", 9999, { total: 1920, other: 224, handles: 2 })).toBe(SPLIT_LIMITS.right.max);
  });

  it("reserves room for the conversation column", () => {
    expect(clampSplitWidth("right", 720, { total: 1000, other: 224, handles: 2 })).toBe(1000 - 224 - 18 - 340);
    expect(clampSplitWidth("left", 420, { total: 900, other: 300, handles: 2 })).toBe(900 - 300 - 18 - 340);
  });

  it("round-trips persisted widths and ignores invalid values", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => { store.set(key, value); } };
    writeSplitWidths(storage, { left: 260, plan: 480, insight: undefined });
    expect(readSplitWidths(storage)).toEqual({ left: 260, plan: 480, insight: undefined });
    store.set("tagpilot:split-widths", "{bad");
    expect(readSplitWidths(storage)).toEqual({});
    store.set("tagpilot:split-widths", JSON.stringify({ left: 10, plan: 9999, insight: "wide" }));
    expect(readSplitWidths(storage)).toEqual({ left: SPLIT_LIMITS.left.min, plan: SPLIT_LIMITS.right.max, insight: undefined });
  });
});
