import { useState } from "react";
import { submitFeedback, type Candidate, type RetrieveResult } from "./api";

type SuggestTagsProps = {
  result: RetrieveResult;
};

export function SuggestTagsCard({ result }: SuggestTagsProps) {
  const [savedId, setSavedId] = useState<number | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const candidates = result.candidates || [];

  async function accept(row: Candidate) {
    if (!row.tag_id || savedId != null || savingId != null) return;
    setSavingId(row.tag_id);
    setError("");
    try {
      await submitFeedback({
        traceId: result.trace_id,
        buildId: result.build_id,
        snapshotId: result.snapshot_id,
        recommendedTagId: row.tag_id,
        finalTagId: row.tag_id,
        action: "ACCEPT",
      });
      setSavedId(row.tag_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "反馈失败");
    } finally {
      setSavingId(null);
    }
  }

  if (candidates.length === 0) {
    return <div className="suggest-empty">当前可用范围内没有候选标签。</div>;
  }

  return (
    <div className="suggest-card">
      <table>
        <thead>
          <tr>
            <th>候选标签</th>
            <th>所属标签族</th>
            <th>原始码值</th>
            <th>反馈</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((row, index) => (
            <tr key={row.tag_id || index}>
              <td>{row.name || "-"}</td>
              <td>{row.family_key || "-"}</td>
              <td>{row.code || "-"}</td>
              <td>
                <button
                  type="button"
                  className="suggest-accept"
                  disabled={savedId != null || savingId != null || !row.tag_id}
                  onClick={() => accept(row)}
                >
                  {savedId === row.tag_id ? "已记录" : savingId === row.tag_id ? "提交中" : "符合需求"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {savedId != null ? <p className="suggest-note">反馈已记录。</p> : null}
      {error ? <p className="suggest-error">{error}</p> : null}
    </div>
  );
}
