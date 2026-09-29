import { useEffect, useState } from "react";
import type { PendingItem } from "./agentTypes";

export function PendingCard({ items, disabled, canRemove, onConfirm, onRemove, onEdit, onDiscuss }: {
  items: PendingItem[]; disabled: boolean; canRemove: boolean; onConfirm: (id: string) => void;
  onRemove: (item: PendingItem) => void; onEdit: (id: string) => void; onDiscuss: (text: string) => void;
}) {
  const [index, setIndex] = useState(0);
  const [choice, setChoice] = useState("adopt");
  const item = items[index % Math.max(items.length, 1)];
  useEffect(() => { setChoice("adopt"); }, [item?.id]);
  if (!item) return null;
  return <section className="pending-card" aria-label="待处理事项">
    <div className="pending-heading"><strong>需要你确认</strong><span>第 {index % items.length + 1}/{items.length} 项</span></div>
    <p className="pending-title">{item.title}</p>
    <p>{item.message}</p>
    {item.kind === "assumption" ? <fieldset className="pending-options"><legend className="sr-only">选择业务口径</legend>
      <label><input type="radio" name="business-definition" value="adopt" disabled={disabled} checked={choice === "adopt"} onChange={() => setChoice("adopt")} />采用上述口径</label>
      <label><input type="radio" name="business-definition" value="custom" disabled={disabled} checked={choice === "custom"} onChange={() => setChoice("custom")} />我自己说</label>
    </fieldset> : null}
    <div className="pending-actions">
      {item.kind === "assumption" ? <button className="primary" disabled={disabled} onClick={() => choice === "adopt" && item.clause_id ? onConfirm(item.clause_id) : onDiscuss(`“${item.title}”，我采用的业务口径是：`)}>确认</button> :
        item.kind === "gap" ? <><button disabled={disabled || !canRemove} onClick={() => onRemove(item)}>去掉这项要求</button>
          <button className="primary" disabled={disabled} onClick={() => onDiscuss(`我想调整这项要求：“${item.title}”。我可接受的范围是：`)}>换个说法</button></> :
          item.clause_id && item.kind !== "question" ? <button className="primary" disabled={disabled} onClick={() => onEdit(item.clause_id!)}>补充这项条件</button> :
            <button className="primary" disabled={disabled} onClick={() => onDiscuss(item.kind === "question" ? "" : `请帮我处理这项条件：${item.message}`)}>在对话中{item.kind === "question" ? "确认" : "补充"}</button>}
      {items.length > 1 ? <button className="text-button" disabled={disabled} onClick={() => setIndex((i) => (i + 1) % items.length)}>先跳过</button> : null}
    </div>
    {items.length > 1 ? <span className="pending-note">跳过仅切换查看，待处理事项仍须解决。</span> : null}
  </section>;
}
