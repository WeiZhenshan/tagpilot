const paths = {
  copy: "M8 7V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2M5 8h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z",
  quote: "M10 6H5a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h3l-2 4m15-13h-5a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h3l-2 4",
  send: "m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13",
  stop: "M7 7h10v10H7z",
  run: "M8 5v14l11-7L8 5Z",
  save: "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2ZM7 3v6h10V4M7 21v-8h10v8",
  edit: "m15 4 5 5M4 20l5-1L20 8a2.1 2.1 0 0 0-4-4L5 15l-1 5Z",
  info: "M12 11v6M12 7h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  close: "m6 6 12 12M18 6 6 18",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  chevron: "m9 18 6-6-6-6",
};

export function ActionIcon({ kind, className, open }: { kind: keyof typeof paths; className?: string; open?: boolean }) {
  return <svg className={className} data-open={open || undefined} viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[kind]} /></svg>;
}
