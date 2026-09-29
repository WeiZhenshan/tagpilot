import { expect, it } from "vitest";
import { stagedQuestions } from "./clarification";

it("旧问题先确定指标，其他需求的阈值仍可回答", () => {
  const definition = { requirement_id: "R1", prompt: "指标？", reason: "MULTIPLE_PUBLISHED_DEFINITIONS" };
  const threshold = { requirement_id: "R1", prompt: "档位？", reason: "THRESHOLD_MISSING" };
  expect(stagedQuestions([definition, threshold])).toEqual([definition]);
  expect(stagedQuestions([threshold])).toEqual([threshold]);
  expect(stagedQuestions([definition, { ...threshold, requirement_id: "R2" }])).toHaveLength(2);
});
