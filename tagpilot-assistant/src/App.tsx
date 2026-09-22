import { useCallback, useEffect, useRef, useState } from "react";
import {
  listLibraries,
  apiRequest,
  readAdminToken,
  type LibraryRow,
} from "./api";
import * as api from "./agentApi";
import { AgentConversation } from "./AgentConversation";
import { PlanPanel } from "./PlanPanel";
import {
  busy,
  stateText,
  planStateText,
  type Thread,
  type ThreadRow,
  type Plan,
} from "./agentTypes";
import { parseWorkbenchQuery, requestBackToWorkbench } from "./workbench";
export function App() {
  const initial = useRef(parseWorkbenchQuery(window.location.search)).current;
  const [libraries, setLibraries] = useState<LibraryRow[]>([]);
  const [library, setLibrary] = useState<number | undefined>(initial.libraryId);
  const [history, setHistory] = useState<ThreadRow[]>([]);
  const [thread, setThread] = useState<Thread | null>(null);
  const current = useRef<Thread | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState("chat");
  const [rename, setRename] = useState(false);
  const [title, setTitle] = useState("");
  const [sample, setSample] = useState<Record<string, unknown> | null>(null);
  const sampleDialog = useRef<HTMLDialogElement>(null);
  const sampleTrigger = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!sample) return;
    sampleDialog.current?.showModal();
    return () => {
      sampleTrigger.current?.focus();
    };
  }, [sample]);
  const generation = useRef(0);
  const inflight = useRef(false);
  const update = useCallback((value: Thread) => {
    current.current = value;
    setThread(value);
    setLibrary(value.library_id);
    const url = new URL(location.href);
    url.searchParams.set("threadId", value.thread_id);
    historyReplace(url);
  }, []);
  function historyReplace(url: URL) {
    window.history.replaceState(null, "", url);
  }
  const reloadHistory = useCallback(async () => {
    setHistory(await api.listThreads(archived, page));
  }, [archived, page]);
  useEffect(() => {
    let dead = false;
    void Promise.all([
      listLibraries(),
      apiRequest<{ user: { userId: number } }>("/getInfo"),
    ])
      .then(([r]) => {
        if (!dead) {
          setLibraries(r.rows || []);
          setLibrary((v) => v || r.rows?.[0]?.libraryId);
        }
      })
      .catch((e) => !dead && setError(e.message));
    return () => {
      dead = true;
    };
  }, []);
  useEffect(() => {
    void reloadHistory().catch((e) => setError(e.message));
  }, [reloadHistory]);
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("threadId");
    if (id)
      void api
        .getThread(id)
        .then(update)
        .catch((e) => setError(e.message));
  }, [update]);
  useEffect(() => {
    if (!thread || !busy(thread)) return;
    const id = thread.thread_id;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    const poll = async () => {
      try {
        const value = await api.readUpdates(id, controller.signal);
        if (controller.signal.aborted || current.current?.thread_id !== id)
          return;
        update(value);
        failures = 0;
        setError("");
        if (busy(value)) timer = setTimeout(poll, 1000);
        else void reloadHistory();
      } catch (e) {
        if (controller.signal.aborted) return;
        failures++;
        setError("连接暂时中断，正在恢复。不会重复提交需求。");
        timer = setTimeout(poll, Math.min(1000 * 2 ** failures, 10000));
      }
    };
    timer = setTimeout(poll, 400);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [thread?.thread_id, thread?.status, update, reloadHistory]);
  useEffect(() => {
    const initialToken = readAdminToken();
    const resetSession = () => {
      current.current = null;
      setThread(null);
      setHistory([]);
      setSample(null);
      const url = new URL(location.href);
      url.searchParams.delete("threadId");
      location.replace(url.toString());
    };
    const checkSession = () => {
      if (readAdminToken() !== initialToken) resetSession();
    };
    window.addEventListener("focus", checkSession);
    window.addEventListener("tagpilot-agent:session-changed", resetSession);
    const receive = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.source !== window.parent) return;
      if (
        e.data?.type === "tagpilot-agent:theme" &&
        /^#[0-9a-f]{6}$/i.test(e.data.color)
      )
        document.documentElement.style.setProperty("--accent", e.data.color);
      if (e.data?.type === "tagpilot-agent:identity-changed") {
        resetSession();
      }
    };
    window.addEventListener("message", receive);
    window.parent.postMessage(
      { type: "tagpilot-agent:ready" },
      location.origin
    );
    return () => {
      window.removeEventListener("message", receive);
      window.removeEventListener("focus", checkSession);
      window.removeEventListener(
        "tagpilot-agent:session-changed",
        resetSession
      );
    };
  }, []);
  async function operation(fn: () => Promise<void>) {
    if (inflight.current) return;
    inflight.current = true;
    setPending(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败，请重试");
    } finally {
      inflight.current = false;
      setPending(false);
    }
  }
  async function select(id: string) {
    const seq = ++generation.current;
    await operation(async () => {
      const t = await api.getThread(id);
      if (seq === generation.current) {
        update(t);
        setRename(false);
        setSample(null);
        setTab("chat");
      }
    });
  }
  async function fresh(next = library) {
    if (!next) return;
    await operation(async () => {
      generation.current++;
      update(await api.createThread(next));
      setTab("chat");
      await reloadHistory();
    });
  }
  async function send(text: string) {
    await operation(async () => {
      if (!library) return;
      let t = current.current;
      if (!t) t = await api.createThread(library);
      update(t);
      update(await api.startRun(t, text));
      await reloadHistory();
    });
  }
  const act = (fn: (t: Thread) => Promise<Thread>) =>
    operation(async () => {
      if (current.current) update(await fn(current.current));
    });
  const savePlan = (plan: Plan) =>
    void act((t) =>
      t.status === "WAITING"
        ? api.resumeRun(t, { plan })
        : api.startRun(t, "按编辑后的条件核验圈选方案", plan)
    );
  const openGroup = (id: number) =>
    requestBackToWorkbench(`/objectgroup/group-edit/index?groupId=${id}`);
  async function create(name: string) {
    await operation(async () => {
      const t = current.current;
      if (!t) return;
      try {
        const result = await api.createGroup(t, name);
        update({ ...t, execution: { ...result, revision: t.revision } });
      } catch (e) {
        const result = await api.groupStatus(t);
        if (result.group_id)
          update({
            ...t,
            execution: { group_id: result.group_id, revision: t.revision },
          });
        else throw e;
      }
    });
  }
  return (
    <div className={`workbench mobile-${tab}`}>
      <header className="topbar">
        <button
          className="back-button"
          onClick={() => requestBackToWorkbench(initial.from)}
          aria-label="返回标签系统"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
          >
            <path d="m14 6-6 6 6 6" />
          </svg>
        </button>
        <strong>客群圈选</strong>
        <span className="header-divider" />
        <label className="library-picker">
          <span>标签库</span>
          <select
            aria-label="当前标签库"
            value={library || ""}
            disabled={pending || busy(thread) || thread?.status === "WAITING"}
            onChange={(e) => void fresh(Number(e.target.value))}
          >
            <option value="">请选择标签库</option>
            {libraries.map((l) => (
              <option key={l.libraryId} value={l.libraryId}>
                {l.libraryName}
              </option>
            ))}
          </select>
        </label>
        <span className="topbar-status" role="status">
          {pending
            ? "正在保存…"
            : thread
            ? (thread.status === "COMPLETED" && thread.plan?.plan_status ? planStateText[thread.plan.plan_status] : stateText[thread.status])
            : "准备就绪"}
        </span>
      </header>
      <div className="body">
        <aside className="history-rail">
          <button
            className="new-thread"
            disabled={pending || !library}
            onClick={() => void fresh()}
          >
            新建圈选
          </button>
          <input
            className="history-search"
            aria-label="搜索会话"
            placeholder="搜索当前页会话"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="history-heading">
            <span>{archived ? "已归档" : "最近圈选"}</span>
            <button
              className="text-button"
              onClick={() => {
                setArchived(!archived);
                setPage(1);
              }}
            >
              {archived ? "返回最近" : "查看归档"}
            </button>
          </div>
          <nav aria-label="圈选会话">
            {history
              .filter((t) => t.title.includes(search))
              .map((t) => (
                <button
                  className={`history-item ${
                    t.threadId === thread?.thread_id ? "selected" : ""
                  }`}
                  key={t.threadId}
                  disabled={pending}
                  onClick={() => void select(t.threadId)}
                >
                  <span>{t.title}</span>
                  <small>
                    {new Date(t.updateTime).toLocaleDateString("zh-CN")}
                  </small>
                </button>
              ))}
          </nav>
          {!history.length ? (
            <p className="history-empty">
              {archived ? "没有已归档的圈选" : "你的圈选任务会保存在这里"}
            </p>
          ) : null}
          <div className="history-pages">
            <button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              上一页
            </button>
            <span>{page}</span>
            <button
              disabled={history.length < 30}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
        </aside>
        <main className="conversation">
          <div className="conversation-heading">
            {rename ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void operation(async () => {
                    if (thread) {
                      update(
                        await api.changeThread(thread.thread_id, { title })
                      );
                      setRename(false);
                      await reloadHistory();
                    }
                  });
                }}
              >
                <input
                  autoFocus
                  aria-label="会话标题"
                  maxLength={120}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <button disabled={pending}>保存</button>
                <button type="button" onClick={() => setRename(false)}>
                  取消
                </button>
              </form>
            ) : (
              <>
                <span>{thread?.title || "新的圈选"}</span>
                {thread ? (
                  <div>
                    <button
                      className="text-button"
                      onClick={() => {
                        setTitle(thread.title);
                        setRename(true);
                      }}
                    >
                      重命名
                    </button>
                    <button
                      className="text-button"
                      disabled={
                        pending || busy(thread) || thread.status === "WAITING"
                      }
                      onClick={() =>
                        void operation(async () => {
                          update(
                            await api.changeThread(thread.thread_id, {
                              archived: !thread.archived,
                            })
                          );
                          await reloadHistory();
                        })
                      }
                    >
                      {thread.archived ? "恢复" : "归档"}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
          <div className="mobile-tabs" role="tablist" aria-label="工作台分区">
            <button
              role="tab"
              aria-selected={tab === "history"}
              onClick={() => setTab("history")}
            >
              历史
            </button>
            <button
              role="tab"
              aria-selected={tab === "chat"}
              onClick={() => setTab("chat")}
            >
              对话
            </button>
            <button
              role="tab"
              aria-selected={tab === "plan"}
              onClick={() => setTab("plan")}
            >
              圈选方案
            </button>
          </div>
          {error ? (
            <div className="banner error" role="alert">
              <span>{error}</span>
              <button
                onClick={() => {
                  setError("");
                  if (thread) void select(thread.thread_id);
                }}
              >
                刷新状态
              </button>
            </div>
          ) : null}
          <AgentConversation
            thread={thread}
            disabled={!library || !!thread?.archived}
            pending={pending}
            onSend={send}
            onCancel={() => void act(api.cancelRun)}
            onAnswer={(a) => void act((t) => api.resumeRun(t, a))}
            onRetry={() => void act((t) => api.resumeRun(t))}
          />
        </main>
        <PlanPanel
          thread={thread}
          pending={pending}
          onSave={savePlan}
          onCount={() => void act(api.countPlan)}
          onCreate={(name) => void create(name)}
          onPreview={() => {
            sampleTrigger.current = document.activeElement as HTMLElement;
            void operation(async () => {
              if (thread) setSample(await api.previewPlan(thread));
            });
          }}
          onOpenGroup={openGroup}
        />
      </div>
      {sample ? (
        <dialog
          ref={sampleDialog}
          onCancel={() => setSample(null)}
          onKeyDown={(e) => {
            if (e.key !== "Tab") return;
            const items = Array.from(
              e.currentTarget.querySelectorAll<HTMLElement>(
                'button:not(:disabled), input, select, [tabindex="0"]'
              )
            );
            const first = items[0],
              last = items[items.length - 1];
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }}
          className="sample-overlay"
          aria-modal="true"
          aria-label="客户样例"
        >
          <div className="sample-dialog">
            <div className="panel-heading">
              <h2>客户样例</h2>
              <button onClick={() => setSample(null)}>关闭</button>
            </div>
            <p className="muted">
              只展示当前权限允许的样例；未写入会话或发送给模型。
            </p>
            <Sample data={sample} />
          </div>
        </dialog>
      ) : null}
    </div>
  );
}
function Sample({ data }: { data: Record<string, unknown> }) {
  const rows = (data.displayRows || data.rows || data.data || []) as Record<
    string,
    unknown
  >[];
  if (!Array.isArray(rows) || !rows.length)
    return <p>没有可展示的客户样例。</p>;
  const keys = Object.keys(rows[0]);
  return (
    <div className="sample-table">
      <table>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k}>{String(r[k] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
