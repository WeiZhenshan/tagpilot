import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
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
import {
  parseWorkbenchQuery,
  requestBackToWorkbench,
  requestLogout,
} from "./workbench";

type UserIdentity = {
  userId: number;
  userName?: string;
  nickName?: string;
  avatar?: string;
};

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
  const [tab, setTab] = useState("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem("tagpilot:history-collapsed") === "1"
  );
  const [mobile, setMobile] = useState(() =>
    window.matchMedia("(max-width: 760px)").matches
  );
  const [profile, setProfile] = useState<UserIdentity | null>(null);
  const [accountOpen, setAccountOpen] = useState(false);
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [deleteCandidate, setDeleteCandidate] = useState<ThreadRow | null>(null);
  const [sample, setSample] = useState<Record<string, unknown> | null>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const deleteTrigger = useRef<HTMLElement | null>(null);
  const sampleDialog = useRef<HTMLDialogElement>(null);
  const sampleTrigger = useRef<HTMLElement | null>(null);
  const account = useRef<HTMLDivElement>(null);
  const cancelRename = useRef(false);
  useEffect(() => {
    if (!deleteCandidate) return;
    deleteDialog.current?.showModal();
    return () => {
      deleteTrigger.current?.focus();
    };
  }, [deleteCandidate]);
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
    setHistory(await api.listThreads(archived));
  }, [archived]);
  const visibleHistory = useMemo(
    () => history.filter((item) => item.title.includes(search.trim())),
    [history, search]
  );
  useEffect(() => {
    let dead = false;
    void Promise.all([
      listLibraries(),
      apiRequest<{ user: UserIdentity }>("/getInfo"),
    ])
      .then(([r, info]) => {
        if (!dead) {
          setLibraries(r.rows || []);
          setLibrary((v) => v || r.rows?.[0]?.libraryId);
          setProfile(info.user);
        }
      })
      .catch((e) => !dead && setError(e.message));
    return () => {
      dead = true;
    };
  }, []);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const sync = () => setMobile(media.matches);
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  useEffect(() => {
    if (!accountOpen) return;
    const dismiss = (event: PointerEvent) => {
      if (!account.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAccountOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [accountOpen]);
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
        setSample(null);
        setTab("chat");
      }
    });
  }
  function fresh(next = library) {
    if (!next) return;
    generation.current++;
    current.current = null;
    setThread(null);
    setLibrary(next);
    setSample(null);
    setEditingThreadId(null);
    setTab("chat");
    const url = new URL(location.href);
    url.searchParams.delete("threadId");
    historyReplace(url);
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
  const toggleSidebar = () => {
    if (mobile) {
      setTab((value) => (value === "history" ? "chat" : "history"));
      return;
    }
    setSidebarCollapsed((value) => {
      localStorage.setItem("tagpilot:history-collapsed", value ? "0" : "1");
      return !value;
    });
  };
  const startRename = (item: ThreadRow) => {
    cancelRename.current = false;
    setEditingThreadId(item.threadId);
    setEditingTitle(item.title);
  };
  const finishRename = (item: ThreadRow) => {
    if (cancelRename.current) {
      cancelRename.current = false;
      setEditingThreadId(null);
      return;
    }
    const next = editingTitle.trim();
    setEditingThreadId(null);
    if (!next || next === item.title) return;
    void operation(async () => {
      const changed = await api.changeThread(item.threadId, { title: next });
      if (current.current?.thread_id === item.threadId) update(changed);
      await reloadHistory();
    });
  };
  const changeHistoryItem = (item: ThreadRow, change: Record<string, boolean>) =>
    void operation(async () => {
      const changed = await api.changeThread(item.threadId, change);
      if (current.current?.thread_id === item.threadId) update(changed);
      await reloadHistory();
    });
  const deleteHistoryItem = (item: ThreadRow) =>
    void operation(async () => {
      setDeleteCandidate(null);
      await api.deleteThread(item.threadId);
      if (current.current?.thread_id === item.threadId) {
        generation.current++;
        current.current = null;
        setThread(null);
        setSample(null);
        const url = new URL(location.href);
        url.searchParams.delete("threadId");
        historyReplace(url);
      }
      await reloadHistory();
    });
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
    <div
      className={`workbench mobile-${tab} ${
        sidebarCollapsed ? "sidebar-collapsed" : ""
      }`}
    >
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
        <button
          className="sidebar-toggle"
          onClick={toggleSidebar}
          aria-label={
            mobile
              ? tab === "history"
                ? "收起历史侧边栏"
                : "展开历史侧边栏"
              : sidebarCollapsed
              ? "展开历史侧边栏"
              : "收起历史侧边栏"
          }
          aria-expanded={mobile ? tab === "history" : !sidebarCollapsed}
          title={
            mobile
              ? tab === "history"
                ? "收起侧边栏"
                : "展开侧边栏"
              : sidebarCollapsed
              ? "展开侧边栏"
              : "收起侧边栏"
          }
        >
          <SidebarIcon
            collapsed={mobile ? tab !== "history" : sidebarCollapsed}
          />
        </button>
        <strong>客群圈选</strong>
        <span className="header-divider" />
        <div className="library-picker">
          <span>标签库</span>
          <LibraryPicker
            libraries={libraries}
            value={library || ""}
            disabled={pending || busy(thread) || thread?.status === "WAITING"}
            onChange={fresh}
          />
        </div>
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
            onClick={() => fresh()}
          >
            新建圈选
          </button>
          <input
            className="history-search"
            aria-label="搜索会话"
            placeholder="搜索会话"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="history-heading">
            <span>{archived ? "已归档" : "最近圈选"}</span>
          </div>
          <nav aria-label="圈选会话">
            {visibleHistory.map((item) => (
              <div
                className={`history-item ${
                  item.threadId === thread?.thread_id ? "selected" : ""
                }`}
                key={item.threadId}
              >
                {editingThreadId === item.threadId ? (
                  <input
                    autoFocus
                    className="history-rename"
                    aria-label={`编辑会话名称：${item.title}`}
                    maxLength={120}
                    value={editingTitle}
                    onChange={(event) => setEditingTitle(event.target.value)}
                    onBlur={() => finishRename(item)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        event.currentTarget.blur();
                      }
                      if (event.key === "Escape") {
                        event.preventDefault();
                        cancelRename.current = true;
                        event.currentTarget.blur();
                      }
                    }}
                  />
                ) : (
                  <button
                    className="history-select"
                    aria-disabled={pending}
                    onClick={() => void select(item.threadId)}
                    onDoubleClick={(event) => {
                      event.preventDefault();
                      startRename(item);
                    }}
                    title={item.title}
                  >
                    <span className="history-title">
                      {item.pinned === "1" && !archived ? (
                        <span className="history-pinned" aria-hidden="true">
                          <PinIcon filled />
                        </span>
                      ) : null}
                      <span className="history-title-text">{item.title}</span>
                    </span>
                  </button>
                )}
                {editingThreadId !== item.threadId ? (
                  <div className="history-actions">
                    {!archived ? (
                      <button
                        disabled={pending}
                        onClick={() =>
                          changeHistoryItem(item, {
                            pinned: item.pinned !== "1",
                          })
                        }
                        aria-label={
                          item.pinned === "1"
                            ? `取消置顶：${item.title}`
                            : `置顶：${item.title}`
                        }
                        data-tooltip={item.pinned === "1" ? "取消置顶" : "置顶"}
                      >
                        <PinIcon filled={item.pinned === "1"} />
                      </button>
                    ) : null}
                    <button
                      disabled={
                        pending ||
                        (item.threadId === thread?.thread_id &&
                          !!thread &&
                          (busy(thread) || thread.status === "WAITING"))
                      }
                      onClick={() =>
                        changeHistoryItem(item, { archived: !archived })
                      }
                      aria-label={
                        archived
                          ? `取消归档：${item.title}`
                          : `归档会话：${item.title}`
                      }
                      data-tooltip={archived ? "取消归档" : "归档"}
                    >
                      <ArchiveIcon restore={archived} />
                    </button>
                    {archived ? (
                      <button
                        disabled={pending}
                        onClick={(event) => {
                          deleteTrigger.current = event.currentTarget;
                          setDeleteCandidate(item);
                        }}
                        aria-label={`删除：${item.title}`}
                        data-tooltip="删除"
                      >
                        <TrashIcon />
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}
          </nav>
          {!visibleHistory.length ? (
            <p className="history-empty">
              {search
                ? "没有匹配的会话"
                : archived
                ? "没有已归档的圈选"
                : "你的圈选任务会保存在这里"}
            </p>
          ) : null}
          <div className="account" ref={account}>
            {accountOpen ? (
              <div className="account-menu" role="menu" aria-label="个人菜单">
                <button
                  role="menuitem"
                  onClick={() => requestBackToWorkbench("/user/profile")}
                >
                  <UserIcon />
                  <span>个人中心</span>
                </button>
                <button
                  role="menuitem"
                  onClick={() => {
                    setArchived((value) => !value);
                    setAccountOpen(false);
                    if (mobile) setTab("history");
                  }}
                >
                  <ArchiveIcon restore={archived} />
                  <span>{archived ? "返回最近会话" : "查看归档"}</span>
                </button>
                <span className="account-menu-divider" />
                <button
                  role="menuitem"
                  className="logout-item"
                  onClick={() => {
                    setAccountOpen(false);
                    requestLogout();
                  }}
                >
                  <LogoutIcon />
                  <span>退出登录</span>
                </button>
              </div>
            ) : null}
            <button
              className="account-button"
              aria-haspopup="menu"
              aria-expanded={accountOpen}
              onClick={() => setAccountOpen((value) => !value)}
            >
              <span className="account-avatar" aria-hidden="true">
                {profile?.nickName?.trim()?.slice(0, 1) ||
                  profile?.userName?.trim()?.slice(0, 1) ||
                  "用"}
              </span>
              <span className="account-copy">
                <strong>{profile?.nickName || profile?.userName || "当前用户"}</strong>
                <small>{profile?.userName || "标签系统账号"}</small>
              </span>
              <ChevronIcon open={accountOpen} />
            </button>
          </div>
        </aside>
        <main className="conversation">
          <div className="conversation-heading">
            <span>{thread?.title || "新的圈选"}</span>
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
          onRefine={send}
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
      {deleteCandidate ? (
        <dialog
          ref={deleteDialog}
          onCancel={() => setDeleteCandidate(null)}
          onKeyDown={(event) => {
            if (event.key !== "Tab") return;
            const items = Array.from(
              event.currentTarget.querySelectorAll<HTMLElement>(
                'button:not(:disabled), [tabindex="0"]'
              )
            );
            const first = items[0],
              last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }}
          className="confirm-overlay"
          aria-modal="true"
          aria-labelledby="delete-thread-title"
        >
          <div className="confirm-dialog">
            <h2 id="delete-thread-title">永久删除会话？</h2>
            <p>
              删除「{deleteCandidate.title}」后，对话、圈选方案和处理记录都无法恢复。
            </p>
            <div className="confirm-actions">
              <button autoFocus onClick={() => setDeleteCandidate(null)}>
                取消
              </button>
              <button
                className="danger-button"
                disabled={pending}
                onClick={() => deleteHistoryItem(deleteCandidate)}
              >
                永久删除
              </button>
            </div>
          </div>
        </dialog>
      ) : null}
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

function SidebarIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3.5" y="4" width="17" height="16" rx="2" />
      <path d="M9 4v16" />
      <path d={collapsed ? "m14 9 3 3-3 3" : "m17 9-3 3 3 3"} />
    </svg>
  );
}

function LibraryPicker({
  libraries,
  value,
  disabled,
  onChange,
}: {
  libraries: LibraryRow[];
  value: number | "";
  disabled: boolean;
  onChange: (libraryId: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const listboxId = useId();
  const selectedIndex = libraries.findIndex((item) => item.libraryId === value);
  const selected = selectedIndex >= 0 ? libraries[selectedIndex] : undefined;

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) window.requestAnimationFrame(() => trigger.current?.focus());
  };
  const openAt = (index = Math.max(selectedIndex, 0)) => {
    if (disabled || !libraries.length) return;
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
    const next = (origin + offset + libraries.length) % libraries.length;
    optionRefs.current[next]?.focus();
  };

  return (
    <div
      className="library-select"
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
            : openAt(selectedIndex >= 0 ? selectedIndex : libraries.length - 1);
        }
        if (event.key === "Home" && open) {
          event.preventDefault();
          optionRefs.current[0]?.focus();
        }
        if (event.key === "End" && open) {
          event.preventDefault();
          optionRefs.current[libraries.length - 1]?.focus();
        }
      }}
    >
      <button
        ref={trigger}
        type="button"
        className="library-select-trigger"
        aria-label="当前标签库"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        disabled={disabled}
        onClick={() => (open ? close() : openAt())}
      >
        <span>{selected?.libraryName || "请选择标签库"}</span>
        <ChevronIcon open={open} />
      </button>
      {open ? (
        <div
          id={listboxId}
          className="library-options"
          role="listbox"
          aria-label="选择标签库"
        >
          {libraries.map((item, index) => {
            const isSelected = item.libraryId === value;
            return (
              <button
                key={item.libraryId}
                ref={(element) => {
                  optionRefs.current[index] = element;
                }}
                type="button"
                className="library-option"
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  close(true);
                  if (!isSelected) onChange(item.libraryId);
                }}
              >
                <span className="library-option-check" aria-hidden="true">
                  {isSelected ? <CheckIcon /> : null}
                </span>
                <span>{item.libraryName}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function PinIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 4h6l-.8 5 3.3 3.2v1.3h-11v-1.3L9.8 9 9 4Z" />
      <path d="M12 13.5V21" />
    </svg>
  );
}

function ArchiveIcon({ restore = false }: { restore?: boolean }) {
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
      <path d="M4 7.5h16V20H4z" />
      <path d="M3 4h18v3.5H3zM9 11h6" />
      {restore ? <path d="m9 16-2-2 2-2M7 14h5" /> : null}
    </svg>
  );
}

function TrashIcon() {
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
      <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 20c.5-4.1 2.7-6.2 6.5-6.2s6 2.1 6.5 6.2" />
    </svg>
  );
}

function LogoutIcon() {
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
      <path d="M10 5H5v14h5M14 8l4 4-4 4M8 12h10" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
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
