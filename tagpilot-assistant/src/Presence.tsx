import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * 保持挂载的进出场容器：open 变为 false 后继续渲染 180ms，
 * 让 grid-rows 折叠动画播放完再卸载。关闭期间内容不可聚焦。
 */
export function Presence({ open, className = "collapse", children }: { open: boolean; className?: string; children: ReactNode }) {
  const [mounted, setMounted] = useState(open);
  const last = useRef<ReactNode>(children);
  if (open) last.current = children;
  useEffect(() => {
    if (open) { setMounted(true); return; }
    const timer = window.setTimeout(() => setMounted(false), 180);
    return () => window.clearTimeout(timer);
  }, [open]);
  if (!mounted) return null;
  return (
    <div className={className} data-open={open ? "true" : undefined} inert={open ? undefined : true} aria-hidden={open ? undefined : true}>
      <div className="collapse-inner">{open ? children : last.current}</div>
    </div>
  );
}
