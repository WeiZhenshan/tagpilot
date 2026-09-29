import { describe, expect, it } from "vitest";
import { filterTagTree, toggleTags, usedTagIds } from "./tagSelection";
import type { TagTreeNode } from "./agentTypes";
const nodes: TagTreeNode[] = [{ id: "lib-1", label: "库", children: [{ id: "dir-1", label: "资产", children: [
  { id: "tag-1", tagId: 1, label: "余额" }, { id: "tag-2", tagId: 2, label: "客户等级" },
] }] }];
describe("标签上下文选择", () => {
  it("目录批量最多选5项，明确返回超限状态并跳过已在方案中的标签", () => {
    const candidates = Array.from({ length: 8 }, (_, i) => ({ id: i + 1, name: `标签${i + 1}` }));
    const result = toggleTags([], candidates, new Set([1]));
    expect(result.tags.map((t) => t.id)).toEqual([2, 3, 4, 5, 6]); expect(result.limited).toBe(true);
    expect(toggleTags(result.tags, result.tags, new Set()).tags).toEqual([]);
  });
  it("搜索保留目录路径，目录命中保留子树", () => {
    expect(filterTagTree(nodes, "余额")[0].children![0].children!.map((n) => n.tagId)).toEqual([1]);
    expect(filterTagTree(nodes, "资产")[0].children![0].children).toHaveLength(2);
  });
  it("高亮包含派生表达式两侧的标签", () => {
    expect([...usedTagIds({ kind: "DERIVED_PREDICATE", clause_id: "ratio", expression: { kind: "DIV", args: [{ kind: "TAG", tag_id: 1 }, { kind: "TAG", tag_id: 2 }] }, compare_expression: { kind: "TAG", tag_id: 3 } })]).toEqual([1, 2, 3]);
  });
});
