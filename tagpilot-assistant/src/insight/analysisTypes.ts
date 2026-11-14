import type { ChartSpec, Fact } from "./types";

export type ArtifactReference = { target_artifact_id: string; target_artifact_version: number; title?: string };
export type AnalysisPart = {
  id: string;
  version: number;
  status: "COMPLETE" | "PARTIAL" | "BLOCKED";
} & (
  | { type: "text" | "status"; text: string }
  | { type: "chart" | "table"; artifact_id: string; artifact_version: number }
  | { type: "clarification"; prompt: string; options: string[] }
);
export type AnalysisArtifact = {
  id: string;
  version: number;
  spec: ChartSpec;
  facts: Fact[];
  snapshot_id?: string;
  created_at: string;
  context?: string;
  base_revision?: number;
  base_plan_hash?: string;
  bundle?: { queried_at?: string; data_as_of?: string | null; source_version?: number; quality?: { note?: string } };
};

export function artifactFor(artifacts: Record<string, AnalysisArtifact> | undefined, id: string, version: number) {
  const artifact = artifacts?.[`${id}@${version}`];
  return artifact?.id === id && artifact.version === version ? artifact : undefined;
}

export function analysisLimitation(parts: AnalysisPart[] = []) {
  return parts.find((part) => {
    if (part.type === "clarification") return false;
    if (part.status === "BLOCKED" || part.status === "PARTIAL") return true;
    // 早期会话将取数受限写在已完成的文本块中。
    return "text" in part && /被.{0,12}整组抑制|整组统计已抑制|无法给出可核验的分布图/.test(part.text);
  });
}
