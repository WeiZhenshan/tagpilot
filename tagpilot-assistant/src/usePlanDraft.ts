import { useState } from "react";
import { clauseChanged, clauses, type Thread, type Tree } from "./agentTypes";

type DraftState = {
  revision: number;
  hash?: string;
  tree?: Tree;
  undoTree?: Tree;
  confirmedIds: string[];
};

export function usePlanDraft(thread: Thread | null) {
  const [drafts, setDrafts] = useState(new Map<string, DraftState>());
  const base = thread?.plan;
  const entry = thread ? drafts.get(thread.thread_id) : undefined;
  const state = entry && thread && entry.revision === thread.revision && entry.hash === base?.hash ? entry : undefined;
  const confirmedIds = state?.confirmedIds ?? (thread?.confirmed_clause_ids || []).filter((id) =>
    clauses(base?.tree).some((clause) => clause.clause_id === id && clause.status === "BOUND" && clause.assumption_confirmed === true));
  const draft = base && state?.tree ? { ...base, tree: state.tree, valid: false } : base;

  function setDraft(update?: Omit<DraftState, "revision" | "hash">) {
    if (!thread) return;
    setDrafts((previous) => {
      const next = new Map(previous);
      if (update) next.set(thread.thread_id, { ...update, revision: thread.revision, hash: base?.hash });
      else next.delete(thread.thread_id);
      return next;
    });
  }

  function changeTree(tree: Tree) {
    if (!draft) return;
    const before = new Map(clauses(draft.tree).map((clause) => [clause.clause_id, clause]));
    const after = new Map(clauses(tree).map((clause) => [clause.clause_id, clause]));
    setDraft({
      tree,
      undoTree: after.size < before.size ? draft.tree : undefined,
      confirmedIds: confirmedIds.filter((id) => {
        const prior = before.get(id);
        const next = after.get(id);
        return prior && next && !clauseChanged(prior, next);
      }),
    });
  }

  const incomplete = !!base?.valid && !!state?.tree && clauses(state.tree).some((clause) => {
    if (clause.kind === "SCOPE_ALL" || clause.compare_expression || ["is_null", "is_not_null"].includes(clause.operator || "")) return false;
    const values = clause.values ?? [];
    return !values.length || values.some((value) => !value.trim())
      || (clause.operator === "between" && values.length !== 2);
  });

  return {
    draft,
    incomplete,
    dirty: !!state?.tree,
    confirmedIds,
    changeTree,
    confirmAssumption: (ids: string[]) => setDraft({ ...state, confirmedIds: ids }),
    discard: () => setDraft(),
    undoRemoval: state?.undoTree ? () => setDraft({ tree: state.undoTree, confirmedIds }) : undefined,
  };
}

export type PlanDraft = ReturnType<typeof usePlanDraft>;
