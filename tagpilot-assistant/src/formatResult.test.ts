import { describe, expect, it } from "vitest";
import { formatRetrieveText, lastUserText } from "./formatResult";

describe("lastUserText", () => {
  it("reads the latest user text part", () => {
    expect(
      lastUserText([
        { role: "user", content: [{ type: "text", text: "旧查询" }] },
        { role: "assistant", content: [{ type: "text", text: "候选" }] },
        { role: "user", content: [{ type: "text", text: "近30天有异名跨行转入的客户" }] },
      ]),
    ).toBe("近30天有异名跨行转入的客户");
  });
});

describe("formatRetrieveText", () => {
  it("explains a confirmation decision and lists candidates", () => {
    const text = formatRetrieveText({
      decision: "NEEDS_CONFIRMATION",
      snapshot_id: "snap-1",
      build_id: "b-1",
      selector: "exact-evidence-offline",
      model_connected: false,
      dsl_valid: true,
      candidates: [{ name: "异名转入", family_key: "资金往来", code: "1", tag_id: 9 }],
    });
    expect(text).toContain("DSL 已通过门禁");
    expect(text).toContain("异名转入");
    expect(text).toContain("精确证据演示模式");
  });
});
