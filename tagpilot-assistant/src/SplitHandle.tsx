import { useEffect, useRef, useState } from "react";
import { SPLIT_LIMITS, type SplitSide } from "./splitResize";

type Props = {
  side: SplitSide;
  label: string;
  width: number;
  max: number;
  disabled?: boolean;
  onPreview: (width: number) => void;
  onCommit: (width: number) => void;
  onReset: () => void;
};

type Drag = { startX: number; startWidth: number; next: number };

export function SplitHandle({ side, label, width, max, disabled, onPreview, onCommit, onReset }: Props) {
  const drag = useRef<Drag | null>(null);
  const [dragWidth, setDragWidth] = useState<number | null>(null);
  const [flash, setFlash] = useState(false);
  const flashTimer = useRef<number | undefined>(undefined);
  const limits = side === "left" ? SPLIT_LIMITS.left : SPLIT_LIMITS.right;
  const clamp = (value: number) => Math.round(Math.min(Math.max(value, limits.min), Math.max(limits.min, max)));
  const shown = dragWidth ?? width;

  useEffect(() => () => window.clearTimeout(flashTimer.current), []);
  const finish = () => {
    if (!drag.current) return;
    document.body.classList.remove("split-resizing");
    onCommit(drag.current.next);
    drag.current = null;
    setDragWidth(null);
  };
  const flashWidth = (value: number) => {
    setDragWidth(value);
    setFlash(true);
    window.clearTimeout(flashTimer.current);
    flashTimer.current = window.setTimeout(() => { setDragWidth(null); setFlash(false); }, 800);
  };

  return <div
    className={`split-handle split-handle--${side}`}
    role="separator"
    aria-orientation="vertical"
    aria-label={label}
    aria-valuemin={limits.min}
    aria-valuemax={Math.round(Math.max(limits.min, max))}
    aria-valuenow={Math.round(shown)}
    aria-disabled={disabled || undefined}
    tabIndex={disabled ? -1 : 0}
    data-dragging={dragWidth !== null ? "true" : undefined}
    data-show-width={flash ? "true" : undefined}
    data-width={`${Math.round(shown)} px`}
    title="拖动调整宽度，双击恢复默认"
    onPointerDown={(event) => {
      if (disabled || event.button !== 0) return;
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = { startX: event.clientX, startWidth: width, next: width };
      setDragWidth(width);
      document.body.classList.add("split-resizing");
    }}
    onPointerMove={(event) => {
      if (!drag.current) return;
      const delta = side === "left" ? event.clientX - drag.current.startX : drag.current.startX - event.clientX;
      drag.current.next = clamp(drag.current.startWidth + delta);
      setDragWidth(drag.current.next);
      onPreview(drag.current.next);
    }}
    onPointerUp={finish}
    onPointerCancel={finish}
    onDoubleClick={() => { if (!disabled) onReset(); }}
    onKeyDown={(event) => {
      if (disabled) return;
      if (event.key === "Home") { event.preventDefault(); onReset(); return; }
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const step = (event.key === "ArrowRight" ? 16 : -16) * (side === "left" ? 1 : -1);
      const next = clamp(width + step);
      flashWidth(next);
      onCommit(next);
    }}
  ><span className="split-handle-grip" aria-hidden="true" /></div>;
}
