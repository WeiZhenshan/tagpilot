import { useEffect, useMemo, useState } from "react";
import { listLibraries, type LibraryRow } from "./api";
import { RuntimeProvider } from "./RuntimeProvider";
import { ThreadView } from "./ThreadView";
import { parseWorkbenchQuery, requestBackToWorkbench } from "./workbench";

export function App() {
  const initial = useMemo(() => parseWorkbenchQuery(window.location.search), []);
  const [libraries, setLibraries] = useState<LibraryRow[]>([]);
  const [libraryId, setLibraryId] = useState<number | undefined>(initial.libraryId);
  const [threadKey, setThreadKey] = useState(0);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    listLibraries()
      .then((response) => {
        if (cancelled) return;
        const rows = response.rows || [];
        setLibraries(rows);
        setLibraryId((current) => current || (rows.length === 1 ? rows[0].libraryId : current));
      })
      .catch((error: Error) => {
        if (!cancelled) setLoadError(error.message || "无法加载标签库");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = libraries.find((item) => item.libraryId === libraryId);
  const libraryName = selected?.libraryName || initial.libraryName;
  const disabled = !libraryId;
  const placeholder = disabled
    ? "请先选择标签库"
    : "例如：近30天有异名跨行转入的客户";

  function changeLibrary(nextId: string) {
    const parsed = Number(nextId);
    setLibraryId(Number.isFinite(parsed) && parsed > 0 ? parsed : undefined);
    setThreadKey((value) => value + 1);
  }

  return (
    <div className="workbench">
      <header className="topbar">
        <div className="brand">
          <strong>智能体工作台</strong>
          <span>标签选择 · 须人工确认</span>
        </div>
        <label className="library-picker">
          当前标签库
          <select value={libraryId || ""} onChange={(event) => changeLibrary(event.target.value)}>
            <option value="">请选择标签库</option>
            {libraries.map((item) => (
              <option key={item.libraryId} value={item.libraryId}>
                {item.libraryName}
              </option>
            ))}
            {libraryId && !selected && libraryName ? <option value={libraryId}>{libraryName}</option> : null}
          </select>
        </label>
        <button type="button" className="back" onClick={() => requestBackToWorkbench(initial.from)}>
          返回标签工作台
        </button>
      </header>
      {loadError ? <div className="banner error">{loadError}</div> : null}
      <div className="body">
        <aside className="rail">
          <button type="button" className="new-thread" onClick={() => setThreadKey((value) => value + 1)}>
            新对话
          </button>
          <p className="rail-copy">每次查询都走现有 LangGraph 选择图。切换标签库会新开对话，避免串库。</p>
        </aside>
        <main className="main">
          <RuntimeProvider key={`${threadKey}-${libraryId || "none"}`} libraryId={libraryId}>
            <ThreadView disabled={disabled} placeholder={placeholder} />
          </RuntimeProvider>
        </main>
      </div>
    </div>
  );
}
