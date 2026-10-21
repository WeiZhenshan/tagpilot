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
