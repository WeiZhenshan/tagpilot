import { describe, expect, it } from "vitest";
import { isSafeInternalPath, parseWorkbenchQuery } from "./workbench";

describe("parseWorkbenchQuery", () => {
  it("reads library context and a safe from path", () => {
    expect(parseWorkbenchQuery("?libraryId=107&libraryName=个人客户&from=/taglibrary/tags")).toEqual({
      libraryId: 107,
      libraryName: "个人客户",
      groupId: undefined,
      from: "/taglibrary/tags",
    });
  });

  it("rejects protocol-relative from values", () => {
    expect(parseWorkbenchQuery("?from=//evil.example/phish").from).toBe("/taglibrary/list");
  });
  it("仅接受正整数客群编号", () => {
    expect(parseWorkbenchQuery("?groupId=90").groupId).toBe(90);
    expect(parseWorkbenchQuery("?groupId=1.5").groupId).toBeUndefined();
    expect(parseWorkbenchQuery("?groupId=-1").groupId).toBeUndefined();
  });
});

describe("isSafeInternalPath", () => {
  it("allows in-app paths only", () => {
    expect(isSafeInternalPath("/taglibrary/list")).toBe(true);
    expect(isSafeInternalPath("https://example.com")).toBe(false);
  });
});
