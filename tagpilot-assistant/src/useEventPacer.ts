import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "./agentTypes";

export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return reduced;
}

// 首次挂载直接回放快照，仅对后来追加的事件按节奏展示。
export function useEventPacer(events: RunEvent[], runId: string, running: boolean, reduced: boolean) {
  const [count, setCount] = useState(events.length);
  const baseline = useRef({ runId, count: events.length });
  const input = useRef({ events, running, reduced });
  input.current = { events, running, reduced };
  useEffect(() => {
    if (baseline.current.runId !== runId || events.length < count) {
      baseline.current = { runId, count: events.length };
      setCount(events.length);
    } else if (reduced && count !== events.length) setCount(events.length);
  }, [runId, events.length, reduced, count]);
  useEffect(() => {
    if (reduced || count >= events.length) return;
    // 追赶式节奏：积压越多放得越快，目标约 600ms 内追平；运行结束后按 40ms 排空。
    const backlog = events.length - count;
    const step = running ? Math.max(40, Math.min(180, Math.round(600 / Math.max(1, backlog)))) : 40;
    const timer = window.setTimeout(() => setCount((n) => Math.min(input.current.events.length, n + 1)), step);
    return () => window.clearTimeout(timer);
  }, [count, events.length, runId, running, reduced]);
  const visibleCount = baseline.current.runId !== runId || reduced ? events.length : count;
  return { events: events.slice(0, visibleCount), liveFrom: baseline.current.count, draining: !reduced && count < events.length };
}

export function useNarrationText(text: string, animate: boolean) {
  const played = useRef(false);
  const [length, setLength] = useState(animate ? 0 : text.length);
  useEffect(() => {
    if (!animate || played.current) { setLength(text.length); return; }
    setLength(0);
    let revealed = 0;
    // 一段叙述约 600ms 讲完，和事件追赶节奏保持一致；短句放慢、长句加快。
    const step = Math.max(12, Math.min(32, Math.round(600 / Math.max(1, Math.ceil(text.length / 2)))));
    const timer = window.setInterval(() => {
      revealed = Math.min(text.length, revealed + 2);
      setLength(revealed);
      if (revealed === text.length) { played.current = true; window.clearInterval(timer); }
    }, step);
    return () => { window.clearInterval(timer); if (revealed > 0) played.current = true; };
  }, [text, animate]);
  return { text: text.slice(0, animate ? length : text.length), streaming: animate && length < text.length };
}
