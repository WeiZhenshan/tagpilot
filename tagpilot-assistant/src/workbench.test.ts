import { describe, expect, it } from "vitest";
import { isSafeInternalPath, parseWorkbenchQuery } from "./workbench";

describe("parseWorkbenchQuery", () => {
  it("reads library context and a safe from path", () => {
    expect(parseWorkbenchQuery("?libraryId=107&libraryName=个人客户&from=/taglibrary/tags")).toEqual({
      libraryId: 107,
      libraryName: "个人客户",
      from: "/taglibrary/tags",
    });
  });

  it("rejects protocol-relative from values", () => {
    expect(parseWorkbenchQuery("?from=//evil.example/phish").from).toBe("/taglibrary/list");
  });
});

describe("isSafeInternalPath", () => {
  it("allows in-app paths only", () => {
    expect(isSafeInternalPath("/taglibrary/list")).toBe(true);
    expect(isSafeInternalPath("https://example.com")).toBe(false);
  });
});
