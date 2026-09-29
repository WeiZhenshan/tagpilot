import { useEffect, useMemo, useRef, useState } from "react";
import type { ContextTag, TagTreeNode } from "./agentTypes";
import { tagTree } from "./agentApi";
import { filterTagTree, MAX_CONTEXT_TAGS, toggleTags, treeTags } from "./tagSelection";

export function TagChips({ tags, onRemove }: { tags: ContextTag[]; onRemove?: (id: number) => void }) {
  return <div className="tag-chips">{tags.map((tag) => <span className="tag-chip" key={tag.id} title={tag.name}>
    <span>{tag.name}</span>{onRemove ? <button type="button" className="chip-remove" aria-label={`移除标签：${tag.name}`} onClick={() => onRemove(tag.id)}>
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="m4 4 8 8M12 4l-8 8" /></svg>
    </button> : null}
  </span>)}</div>;
}

function Check({ mixed, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { mixed: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (ref.current) ref.current.indeterminate = mixed; }, [mixed]);
  return <input {...props} ref={ref} type="checkbox" />;
}

export function TagTree({ libraryId, selected, used, blockedReason, onChange, onConfirm, onAdd }: {
  libraryId?: number; selected: ContextTag[]; used: Set<number>; blockedReason: string;
  onChange: (tags: ContextTag[]) => void; onConfirm: () => void; onAdd: () => void;
}) {
  const [nodes, setNodes] = useState<TagTreeNode[]>([]);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let dead = false;
    setNodes([]); setQuery(""); setError(""); setNotice(""); setExpanded(new Set());
    if (!libraryId) return;
    setLoading(true);
    void tagTree(libraryId).then((tree) => {
      if (dead) return;
      setNodes(tree); setExpanded(new Set(tree.map((n) => n.id)));
    }).catch((e) => { if (!dead) setError(e.message); }).finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [libraryId, retry]);
  const filtered = useMemo(() => filterTagTree(nodes, query), [nodes, query]);
  const original = useMemo(() => {
    const index = new Map<string, ContextTag[]>();
    const visit = (items: TagTreeNode[]) => items.forEach((n) => { index.set(n.id, treeTags([n])); visit(n.children || []); });
    visit(nodes); return index;
  }, [nodes]);
  const selectedIds = new Set(selected.map((t) => t.id));
  function choose(node: TagTreeNode) {
    const result = toggleTags(selected, original.get(node.id) || [], used);
    onChange(result.tags);
    setNotice(result.limited ? `每轮最多选择 ${MAX_CONTEXT_TAGS} 项，已选满；目录中其余标签未选入。` : "");
  }
  function render(items: TagTreeNode[]): React.ReactNode {
    return <ul className="tag-tree-list">{items.map((node) => {
      const leaf = !!node.tagId;
      const candidates = (original.get(node.id) || []).filter((t) => !used.has(t.id));
      const count = candidates.filter((t) => selectedIds.has(t.id)).length;
      const open = query.trim() ? true : expanded.has(node.id);
      return <li key={node.id}>
        <div className={`tag-tree-row ${leaf && used.has(node.tagId!) ? "tag-in-plan" : ""}`}>
          {!leaf ? <button type="button" className="tag-expand" aria-label={`${open ? "收起" : "展开"}目录：${node.label}`} aria-expanded={open}
            onClick={() => setExpanded((old) => { const next = new Set(old); next.has(node.id) ? next.delete(node.id) : next.add(node.id); return next; })}>
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true" style={{ transform: open ? "rotate(90deg)" : undefined }}><path d="m6 3 5 5-5 5" /></svg>
          </button> : <span className="tag-leaf-space" />}
          <label className="tag-node-label" title={node.dirPath ? `${node.dirPath} / ${node.label}` : node.label}>
            <Check mixed={count > 0 && count < candidates.length} checked={candidates.length > 0 && count === candidates.length}
              disabled={!candidates.length} aria-label={`选择${leaf ? "标签" : "目录"}：${node.label}`} onChange={() => choose(node)} />
            {leaf ? <span className="tag-type-dot" data-type={node.tagType} /> : null}
            <span className="tag-node-name">{node.label}</span>
          </label>
          {leaf && used.has(node.tagId!) ? <span className="tag-used">已在方案中</span> : leaf ? <span className="tag-type">{node.tagType}</span> : null}
        </div>
        {!leaf && open ? render(node.children || []) : null}
      </li>;
    })}</ul>;
  }
  return <section className="tag-browser" aria-label="选择标签上下文">
    <input className="history-search" aria-label="搜索标签或目录" placeholder="搜索标签或目录" value={query} onChange={(e) => setQuery(e.target.value)} />
    <p className="tag-browser-hint">选择标签，逐步确认筛选条件</p>
    <div className="tag-tree-scroll">
      {loading ? <p className="history-empty" role="status">正在加载可用标签…</p> : error ? <div className="tag-tree-error" role="alert"><p>{error}</p><button onClick={() => setRetry((v) => v + 1)}>重新加载</button></div>
        : !libraryId ? <p className="history-empty">请先选择标签库</p> : filtered.length ? render(filtered) : <p className="history-empty">{query ? "没有匹配的标签" : "当前库暂无已发布且可执行的标签"}</p>}
    </div>
    <div className="tag-selection-tray">
      <div className="tag-tray-heading"><span>已选 {selected.length} / {MAX_CONTEXT_TAGS} 项</span><button className="text-button" disabled={!selected.length} onClick={() => { onChange([]); setNotice(""); }}>清空</button></div>
      <TagChips tags={selected} onRemove={(id) => { onChange(selected.filter((t) => t.id !== id)); setNotice(""); }} />
      {notice ? <p className="tag-selection-notice" role="status">{notice}</p> : null}
      {blockedReason ? <p className="tag-blocked-hint">{blockedReason}</p> : null}
      <button className="primary" disabled={!selected.length || !!blockedReason} onClick={onConfirm}>确认并让智能体梳理</button>
      <button disabled={!selected.length || !!blockedReason} onClick={onAdd}>加入输入框</button>
    </div>
  </section>;
}
