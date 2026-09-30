import type { ContextTag, TagTreeNode, Tree, Expression } from "./agentTypes";
import { clauses } from "./agentTypes";

export const MAX_CONTEXT_TAGS = 5;
export function treeTags(nodes: TagTreeNode[]): ContextTag[] {
  return nodes.flatMap((n) => n.tagId ? [{ id: n.tagId, name: n.label }] : treeTags(n.children || []));
}
export function filterTagTree(nodes: TagTreeNode[], query: string): TagTreeNode[] {
  const key = query.trim().toLocaleLowerCase();
  if (!key) return nodes;
  return nodes.flatMap((node) => {
    if (node.label.toLocaleLowerCase().includes(key)) return [node];
    const children = filterTagTree(node.children || [], key);
    return children.length ? [{ ...node, children }] : [];
  });
}
export function toggleTags(selected: ContextTag[], candidates: ContextTag[], used: Set<number>) {
  const available = candidates.filter((t) => !used.has(t.id));
  if (!available.length) return { tags: selected, limited: false };
  if (available.every((t) => selected.some((s) => s.id === t.id))) {
    return { tags: selected.filter((s) => !available.some((t) => t.id === s.id)), limited: false };
  }
  const additions = available.filter((t) => !selected.some((s) => s.id === t.id));
  const capacity = Math.max(0, MAX_CONTEXT_TAGS - selected.length);
  return { tags: [...selected, ...additions.slice(0, capacity)], limited: additions.length > capacity };
}
export function usedTagIds(tree?: Tree): Set<number> {
  const ids = new Set<number>();
  const expression = (e?: Expression) => {
    if (e?.tag_id) ids.add(e.tag_id);
    e?.args?.forEach(expression);
  };
  for (const clause of clauses(tree)) {
    if (clause.tag_id) ids.add(clause.tag_id);
    expression(clause.expression);
    expression(clause.compare_expression);
  }
  return ids;
}
export function selectionMessage(tags: ContextTag[], note = "") {
  return `请基于所选标签「${tags.map((t) => t.name).join("、")}」帮我梳理圈选条件，保留已有条件；缺少的取值和组合关系请向我确认。${note.trim() ? `\n补充说明：${note.trim()}` : ""}`;
}
