import { useEffect, useId, useRef, useState } from "react";

export type ListboxOption = { value: string; label: string };

export function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={open ? "m7 14 5-5 5 5" : "m7 10 5 5 5-5"} />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m5 12 4 4L19 6" />
    </svg>
  );
}

type BaseProps = {
  options: ListboxOption[];
  disabled?: boolean;
  ariaLabel: string;
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
};

type SingleProps = BaseProps & {
  multiple?: false;
  value: string;
  onChange: (value: string) => void;
};

type MultiProps = BaseProps & {
  multiple: true;
  value: string[];
  onChange: (value: string[]) => void;
};

export function ListboxSelect(props: SingleProps | MultiProps) {
  const {
    options,
    disabled = false,
    ariaLabel,
    placeholder = "请选择",
    className,
    triggerClassName,
  } = props;
  const multiple = props.multiple === true;
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const listboxId = useId();

  const selectedValues = multiple
    ? props.value
    : props.value
      ? [props.value]
      : [];
  const selectedIndex = multiple
    ? -1
    : options.findIndex((item) => item.value === props.value);

  const triggerLabel = () => {
    if (!multiple) {
      const hit = options.find((item) => item.value === props.value);
      return hit?.label || placeholder;
    }
    if (!selectedValues.length) return placeholder;
    const labels = selectedValues
      .map((v) => options.find((o) => o.value === v)?.label || v)
      .filter(Boolean);
    return labels.length <= 2
      ? labels.join("、")
      : `已选 ${labels.length} 项`;
  };

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) window.requestAnimationFrame(() => trigger.current?.focus());
  };
  const openAt = (index = Math.max(selectedIndex, 0)) => {
    if (disabled || !options.length) return;
    setOpen(true);
    window.requestAnimationFrame(() => optionRefs.current[index]?.focus());
  };

  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);
  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);

  const moveFocus = (offset: number) => {
    const currentIndex = optionRefs.current.findIndex(
      (option) => option === document.activeElement
    );
    const origin = currentIndex >= 0 ? currentIndex : Math.max(selectedIndex, 0);
    const next = (origin + offset + options.length) % options.length;
    optionRefs.current[next]?.focus();
  };

  const selectSingle = (value: string) => {
    close(true);
    if (!multiple && props.value !== value) props.onChange(value);
  };

  const toggleMulti = (value: string) => {
    if (!multiple) return;
    const set = new Set(props.value);
    if (set.has(value)) set.delete(value);
    else set.add(value);
    props.onChange([...set]);
  };

  const isSelected = (value: string) => selectedValues.includes(value);

  return (
    <div
      className={["library-select", className].filter(Boolean).join(" ")}
      ref={root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOpen(false);
        }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          close(true);
          return;
        }
        if (event.key === "ArrowDown") {
          event.preventDefault();
          open ? moveFocus(1) : openAt();
        }
        if (event.key === "ArrowUp") {
          event.preventDefault();
          open
            ? moveFocus(-1)
            : openAt(selectedIndex >= 0 ? selectedIndex : options.length - 1);
        }
        if (event.key === "Home" && open) {
          event.preventDefault();
          optionRefs.current[0]?.focus();
        }
        if (event.key === "End" && open) {
          event.preventDefault();
          optionRefs.current[options.length - 1]?.focus();
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className={["library-select-trigger", triggerClassName]
          .filter(Boolean)
          .join(" ")}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        disabled={disabled}
        onClick={() => (open ? close() : openAt())}
      >
        <span>{triggerLabel()}</span>
        <ChevronIcon open={open} />
      </button>
      {open ? (
        <div
          id={listboxId}
          className="library-options"
          role="listbox"
          aria-label={ariaLabel}
          aria-multiselectable={multiple || undefined}
        >
          {options.map((item, index) => {
            const selected = isSelected(item.value);
            return (
              <button
                key={item.value}
                ref={(element) => {
                  optionRefs.current[index] = element;
                }}
                type="button"
                className="library-option"
                role="option"
                aria-selected={selected}
                onClick={() =>
                  multiple ? toggleMulti(item.value) : selectSingle(item.value)
                }
              >
                <span className="library-option-check" aria-hidden="true">
                  {selected ? <CheckIcon /> : null}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
