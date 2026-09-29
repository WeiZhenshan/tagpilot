import type { Thread } from "./agentTypes";

export function stagedQuestions(questions: NonNullable<Thread["questions"]>) {
  const definitions = new Set(questions.filter((q) => ["MULTIPLE_PUBLISHED_DEFINITIONS", "CONFLICTING_INTERPRETATIONS", "DEFINITION_MISSING"].includes(q.reason || ""))
    .map((q) => q.requirement_id || q.clause_id));
  return questions.filter((q) => !(q.reason === "THRESHOLD_MISSING" && definitions.has(q.requirement_id || q.clause_id)));
}
