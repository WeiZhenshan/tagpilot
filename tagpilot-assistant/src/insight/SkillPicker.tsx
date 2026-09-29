import { useEffect, useState } from "react";
import { GOLDEN_SKILLS, insightCatalog, type InsightCatalog } from "./insightApi";
export function SkillPicker({ library, selected, onChange }: { library?: number; selected: string[]; onChange: (ids: string[]) => void }) {
  const [catalog, setCatalog] = useState<InsightCatalog>();
  const [error, setError] = useState("");
  useEffect(() => {
    let dead = false; setCatalog(undefined); setError("");
    if (library) void insightCatalog(library).then((value) => { if (!value || !Array.isArray(value.skills) || !Array.isArray(value.versions)) throw new Error("技能目录暂时不可用，请刷新后重试。"); if (!dead) setCatalog(value); }).catch((e) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [library]);
  const published = (id: string) => catalog?.versions.some((v) => v.skill_id === id && v.status === "PUBLISHED" && v.pack_hash === catalog.skills.find((s) => s.manifest.id === id)?.pack_hash);
  return <div className="insight-picker"><h2>客群洞察技能</h2><p>先统计当前方案人数，再运行已发布技能。报告绑定本次客群和数据日期。</p>
    {!library ? <p>请先选择标签库。</p> : error ? <p role="status">{error}</p> : !catalog ? <p role="status">正在读取技能…</p> : <>
      <button type="button" disabled={!GOLDEN_SKILLS.every(published)} onClick={() => onChange(GOLDEN_SKILLS)}>添加大额入金转化包</button>
      {catalog.skills.map(({ manifest: m }) => <section key={m.id}><h3>{m.name}</h3><p>{m.layer} · {m.question}</p><p>样本至少 {m.preconditions.min_sample} 人 · 数据不超过 {m.preconditions.max_stale_days} 天</p><button type="button" disabled={!published(m.id)} aria-pressed={selected.includes(m.id)} onClick={() => onChange(selected.includes(m.id) ? selected.filter((id) => id !== m.id) : [...selected, m.id])}>{!published(m.id) ? "待绑定、复核与发布" : selected.includes(m.id) ? "移除技能" : "添加技能"}</button></section>)}
    </>}
  </div>;
}
