import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
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
import { InsightSummary } from "./insight/InsightSummary";
import { SkillPicker } from "./insight/SkillPicker";
import { GOLDEN_SKILLS, runInsight, skillNames, routeInsight, editInsight, insightFeedback, insightParameterSummary } from "./insight/insightApi";
import "./insight/workbench-insight.css";
const InsightReportPanel = lazy(() => import("./insight/InsightReportPanel").then((m) => ({ default: m.InsightReportPanel })));
import { PlanPanel } from "./PlanPanel";
import { TagTree, TagChips } from "./TagTree";
import { MAX_CONTEXT_TAGS, selectionMessage, usedTagIds } from "./tagSelection";
import { ChevronIcon, ListboxSelect } from "./ListboxSelect";
import {
  busy,
  degradedOf,
  stateText,
  planStateText,
  type Thread,
  type ThreadRow,
  type Plan,
  type ContextTag,
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
  const [highlightedClauses, setHighlightedClauses] = useState<string[]>([]);
  useEffect(() => { setHighlightedClauses([]); }, [thread?.thread_id, thread?.run_id]);
  const [tab, setTab] = useState("chat");
  const [railTab, setRailTab] = useState<"history" | "tags" | "skills">("history");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [insightParameters,setInsightParameters] = useState<Record<string,unknown>>({});
  const [insightNotice,setInsightNotice] = useState("");
  const [rightTab, setRightTab] = useState<"plan" | "insight">("plan");
  const [insightWide, setInsightWide] = useState(false);
  useEffect(() => { setSelectedSkills([]); setInsightParameters({}); setInsightNotice(""); setRightTab("plan"); }, [library, thread?.thread_id]);
  const [selectedTags, setSelectedTags] = useState<ContextTag[]>([]);
  const [contextTags, setContextTags] = useState<ContextTag[]>([]);
  const [tagConfirm, setTagConfirm] = useState(false);
  const [tagNote, setTagNote] = useState("");
  const tagDialog = useRef<HTMLDialogElement>(null);
  const tagTrigger = useRef<HTMLElement | null>(null);
  const usedTags = useMemo(() => usedTagIds(thread?.live_plan?.tree || thread?.plan?.tree), [thread?.live_plan, thread?.plan]);
  useEffect(() => { setSelectedTags([]); setContextTags([]); setTagConfirm(false); }, [library]);
  useEffect(() => {
    setSelectedTags((items) => items.filter((t) => !usedTags.has(t.id)));
    setContextTags((items) => items.filter((t) => !usedTags.has(t.id)));
  }, [usedTags]);
  useEffect(() => {
    if (!tagConfirm) return;
    tagDialog.current?.showModal();
    return () => { tagTrigger.current?.focus(); };
  }, [tagConfirm]);
  const [composerRequest, setComposerRequest] = useState<{ text: string; id: number; focusOnly?: boolean }>();
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
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false);
  const [sample, setSample] = useState<Record<string, unknown> | null>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);
  const deleteAllDialog = useRef<HTMLDialogElement>(null);
  const deleteTrigger = useRef<HTMLElement | null>(null);
  const deleteAllTrigger = useRef<HTMLElement | null>(null);
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
    if (!deleteAllConfirm) return;
    deleteAllDialog.current?.showModal();
    return () => {
      deleteAllTrigger.current?.focus();
    };
  }, [deleteAllConfirm]);
  useEffect(() => {
    if (!sample) return;
    sampleDialog.current?.showModal();
    return () => {
      sampleTrigger.current?.focus();
    };
  }, [sample]);
  const generation = useRef(0);
  const inflight = useRef(false);
  const initialLoad = useRef<Promise<Thread> | null>(null);
  const update = useCallback((value: Thread) => {
    current.current = value;
    setThread(value);
    setLibrary(value.library_id);
    const url = new URL(location.href);
    url.searchParams.set("threadId", value.thread_id);
    url.searchParams.delete("groupId");
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
  const deleteAllBlocked =
    !!thread?.archived &&
    history.some((item) => item.threadId === thread.thread_id) &&
    (busy(thread) || thread.status === "WAITING");
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
    let dead = false;
    const seq = generation.current;
    if (initial.groupId || id) {
      setPending(true); inflight.current = true;
      // StrictMode 会重放 effect；建编辑会话的请求只发一次，重放仅重新订阅结果。
      initialLoad.current ||= initial.groupId ? api.fromGroup(initial.groupId) : api.getThread(id!);
      void initialLoad.current
        .then((value) => {
          if (dead || seq !== generation.current) return;
          update(value);
          if (initial.groupId) { setRailTab("tags"); setSidebarCollapsed(false); void reloadHistory(); }
        }).catch((e) => { if (!dead) setError(e.message); })
        .finally(() => { if (!dead) { setPending(false); inflight.current = false; } });
    }
    return () => { dead = true; };
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
    if (inflight.current) return false;
    inflight.current = true;
    setPending(true);
    setError("");
    try {
      await fn();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败，请重试");
      return false;
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
        setSelectedTags([]); setContextTags([]); setTagConfirm(false);
      }
    });
  }
  function fresh(next = library) {
    if (!next) return;
    generation.current++;
    current.current = null;
    setThread(null);
    setSelectedTags([]); setContextTags([]); setTagConfirm(false);
    setLibrary(next);
    setSample(null);
    setEditingThreadId(null);
    setTab("chat");
    const url = new URL(location.href);
    url.searchParams.delete("threadId");
    url.searchParams.delete("groupId");
    historyReplace(url);
  }
  async function send(text: string, tags: ContextTag[] = [], contextOnly = false) {
    if (!library) return false;
    if (thread && thread.count?.revision === thread.revision && /^(请|帮我)?(分析|洞察)/.test(text)) {
      return operation(async () => { const proposed = await routeInsight(thread,text); setSelectedSkills(proposed.skills); setInsightParameters(proposed.parameters); setInsightNotice("已添加推荐技能，请确认后发送运行。" ); });
    }
    let sent = false;
    await operation(async () => {
      let t = current.current;
      if (!t) t = await api.createThread(library);
      update(t);
      update(await api.startRun(t, text, undefined, crypto.randomUUID(), tags.map((tag) => tag.id), contextOnly));
      sent = true;
      setContextTags((items) => items.filter((tag) => !tags.some((t) => t.id === tag.id)));
      setSelectedTags((items) => items.filter((tag) => !tags.some((t) => t.id === tag.id)));
      setTab("chat");
      await reloadHistory();
    });
    return sent;
  }
  const tagBlocked = !library ? "请先选择标签库" : pending ? "正在保存，请稍候" : thread?.archived ? "会话已归档，恢复后可发送" : busy(thread) ? "正在处理，可先浏览并选择标签" : thread?.status === "WAITING" ? "请先回答当前待补充问题" : "";
  function addTagsToComposer() {
    const merged = [...new Map([...contextTags, ...selectedTags].map((t) => [t.id, t])).values()];
    if (merged.length > MAX_CONTEXT_TAGS) { setError("输入框每轮最多加入5个标签，请先移除部分标签。"); return; }
    setContextTags(merged); setSelectedTags([]); setTab("chat");
    setComposerRequest({ text: "", id: Date.now(), focusOnly: true });
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
  const clearCurrentThread = () => {
    generation.current++;
    current.current = null;
    setThread(null);
    setSelectedTags([]); setContextTags([]); setTagConfirm(false);
    setSample(null);
    const url = new URL(location.href);
    url.searchParams.delete("threadId");
    historyReplace(url);
  };
  const deleteHistoryItem = (item: ThreadRow) =>
    void operation(async () => {
      setDeleteCandidate(null);
      await api.deleteThread(item.threadId);
      if (current.current?.thread_id === item.threadId) clearCurrentThread();
      await reloadHistory();
    });
  const deleteAllArchivedThreads = () =>
    void operation(async () => {
      setDeleteAllConfirm(false);
      const items = [...history];
      for (const item of items) await api.deleteThread(item.threadId);
      if (
        current.current &&
        items.some((item) => item.threadId === current.current?.thread_id)
      ) {
        clearCurrentThread();
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
  function sameInsightSource(source: Thread) {
    const latest = current.current;
    return latest?.thread_id === source.thread_id && latest.revision === source.revision && latest.plan?.hash === source.plan?.hash;
  }
  async function analyze(ids = selectedSkills.length ? selectedSkills : GOLDEN_SKILLS) {
    if (!thread || !thread.plan?.valid || thread.count?.revision !== thread.revision || !thread.capabilities.insight) { setError("请先完成圈选并统计人数，且需要洞察运行权限"); return false; }
    const source = thread;
    return operation(async () => {
      const report = await runInsight(source, ids, insightParameters);
      if (!sameInsightSource(source)) return;
      update({ ...current.current!, insight_report: report }); setSelectedSkills([]); setRightTab("insight"); setTab("plan");
    });
  }
  const insightReady = !!thread?.capabilities.insight && thread.count?.revision === thread.revision && !!thread.plan?.valid && !busy(thread) && !thread.archived;
  return (
    <div
      className={`workbench mobile-${tab} ${insightWide ? "insight-wide" : ""} ${
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
        <span className="topbar-status" role="status">
          {pending
            ? "正在保存…"
            : thread
            ? (thread.status === "COMPLETED" && degradedOf(thread) ? "部分完成" : thread.status === "COMPLETED" && thread.plan?.plan_status ? planStateText[thread.plan.plan_status] : stateText[thread.status])
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
          <div className="rail-tabs" role="tablist" aria-label="侧栏内容">
            <button role="tab" aria-selected={railTab === "history"} aria-controls="rail-history" onClick={() => setRailTab("history")}>会话</button>
            <button role="tab" aria-selected={railTab === "skills"} aria-controls="rail-skills" onClick={() => setRailTab("skills")}>技能</button>
            <button role="tab" aria-selected={railTab === "tags"} aria-controls="rail-tags" onClick={() => setRailTab("tags")}>标签</button>
          </div>
          <div id="rail-skills" role="tabpanel" aria-label="技能" hidden={railTab !== "skills"} className="rail-content"><SkillPicker library={library} selected={selectedSkills} onChange={(ids) => { setSelectedSkills(ids); setInsightParameters({}); setInsightNotice(""); }} /></div>
          <div id="rail-tags" role="tabpanel" aria-label="标签" hidden={railTab !== "tags"} className="rail-content rail-tag-content">
            <TagTree libraryId={library} selected={selectedTags} used={usedTags} blockedReason={tagBlocked} onChange={setSelectedTags}
              onConfirm={() => { tagTrigger.current = document.activeElement as HTMLElement; setTagNote(""); setTagConfirm(true); }} onAdd={addTagsToComposer} />
          </div>
          <div id="rail-history" role="tabpanel" aria-label="会话" hidden={railTab !== "history"} className="rail-content">
          <input
            className="history-search"
            aria-label="搜索会话"
            placeholder="搜索会话"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="history-heading">
            <span>{archived ? "已归档" : "最近圈选"}</span>
            {archived && history.length ? (
              <button
                type="button"
                className="text-button history-delete-all"
                disabled={pending || deleteAllBlocked}
                aria-label="删除全部已归档会话"
                onClick={(event) => {
                  deleteAllTrigger.current = event.currentTarget;
                  setDeleteAllConfirm(true);
                }}
              >
                全部删除
              </button>
            ) : null}
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
                          busy(thread))
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
          </div>
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
                    setRailTab("history");
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
              侧栏
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
              aria-selected={tab === "plan" && rightTab === "plan"}
              onClick={() => { setTab("plan"); setRightTab("plan"); }}
            >
              圈选方案
            </button>
            <button role="tab" aria-selected={tab === "plan" && rightTab === "insight"} onClick={() => { setTab("plan"); setRightTab("insight"); }}>洞察</button>
          </div>
          {error || (thread && ["CANCELLED", "FAILED", "INTERRUPTED"].includes(thread.status) && thread.error) ? (
            <div className="banner error" role="alert">
              <span>{error || thread?.error}</span>
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
          {insightReady && !thread?.insight_report && <div className="insight-entry"><p>人数统计已完成，可继续核验资产结构、产品缺口和机会排序。</p><button type="button" disabled={pending} onClick={() => void analyze()}>运行推荐洞察包</button></div>}
          <AgentConversation
            thread={thread}
            disabled={!library || !!thread?.archived}
            pending={pending}
            composerRequest={composerRequest}
            contextControl={
              <LibraryPicker
                libraries={libraries}
                value={library || ""}
                disabled={pending || busy(thread) || thread?.status === "WAITING"}
                onChange={fresh}
              />
            }
            insightSummary={thread?.insight_report ? <InsightSummary report={thread.insight_report} revision={thread.revision} hash={thread.plan?.hash || ""} onExpand={() => { setRightTab("insight"); setTab("plan"); }} /> : undefined}
            skillChips={selectedSkills.length ? <div><p role="status" className="insight-route-notice">{insightNotice}</p><div className="insight-chips">{selectedSkills.map((id) => <span className="insight-chip" key={id}>{skillNames[id]}<button type="button" aria-label={`移除${skillNames[id]}技能`} onClick={() => setSelectedSkills((items) => items.filter((s) => s !== id))}>移除</button></span>)}</div>{Object.keys(insightParameters).length > 0 && <p className="insight-route-notice">{insightParameterSummary(insightParameters)}</p>}</div> : undefined}
            contextTags={contextTags}
            onRemoveContextTag={(id) => setContextTags((items) => items.filter((t) => t.id !== id))}
            onReveal={(ids) => {
              setHighlightedClauses(ids);
              setTab("plan");
              requestAnimationFrame(() => document.getElementById("agent-plan-editor")?.focus());
            }}
            skillRunDisabled={!insightReady}
            onSend={(text) => selectedSkills.length ? (text.trim() ? send(text) : analyze()) : send(text.trim() ? text : selectionMessage(contextTags), contextTags, !text.trim() && !!contextTags.length)}
            onCancel={() => void act(api.cancelRun)}
            onAnswer={(a) => void act((t) => api.resumeRun(t, a))}
            onRetry={() => void act((t) => api.resumeRun(t))}
            onEdit={() => {
              setTab("plan");
              requestAnimationFrame(() => document.getElementById("agent-plan-editor")?.focus());
            }}
          />
        </main>
        <aside className="insight-right"><div className="insight-sidebar-heading"><button type="button" aria-pressed={rightTab === "plan"} onClick={() => setRightTab("plan")}>圈选方案</button><button type="button" aria-pressed={rightTab === "insight"} onClick={() => setRightTab("insight")}>洞察</button>{rightTab === "insight" && <button type="button" aria-pressed={insightWide} onClick={() => setInsightWide(!insightWide)}>{insightWide ? "收起宽模式" : "宽模式"}</button>}</div>
        {rightTab === "plan" ? <PlanPanel
          highlightedClauses={highlightedClauses}
          thread={thread}
          pending={pending}
          onSave={savePlan}
          onRefine={send}
          onDiscuss={(text) => {
            setTab("chat");
            setComposerRequest({ text, id: Date.now() });
          }}
          onCancel={() => void act(api.cancelRun)}
          onCount={() => void act(api.countPlan)}
          onCreate={(name) => void create(name)}
          onPreview={() => {
            sampleTrigger.current = document.activeElement as HTMLElement;
            void operation(async () => {
              if (thread) setSample(await api.previewPlan(thread));
            });
          }}
          onOpenGroup={openGroup}
        /> : thread?.insight_report ? <Suspense fallback={<p className="insight-empty">正在展开报告…</p>}><InsightReportPanel report={thread.insight_report} currentRevision={thread.revision} currentPlanHash={thread.plan?.hash || ""} onEdit={async (skill, chart, utterance) => {
            if (inflight.current) throw new Error("当前操作尚未完成，请稍后重试");
            const source = thread; let changed: Awaited<ReturnType<typeof editInsight>> | undefined;
            const ok = await operation(async () => {
              changed = await editInsight(source,skill,chart,utterance);
              if (!sameInsightSource(source)) throw new Error("当前方案已变化，请重新打开报告");
              if (changed.report) update({ ...current.current!, insight_report: changed.report });
            });
            if (!ok || !changed) throw new Error("图表核验未完成，请查看当前操作提示");
            return changed;
          }} onConfirmRerun={async (skill, parameters) => {
            const source = current.current; if (!source) return;
            const ok = await operation(async () => {
              const report = await runInsight(source,[skill],{[skill]:parameters});
              if (!sameInsightSource(source)) throw new Error("当前方案已变化，请重新运行");
              update({ ...current.current!, insight_report: report });
            });
            if (!ok) throw new Error("重跑未完成，请查看当前操作提示");
          }} onReviewChange={(utterance) => { setRightTab("plan"); setComposerRequest({ text: utterance, id: Date.now() }); setTab("chat"); }} onFeedback={(rating,category,comment) => insightFeedback(thread.insight_report!.run_id,rating,category,comment)} /></Suspense> : <div className="insight-empty"><p>先统计当前方案人数，再选择已发布技能。</p><button type="button" disabled={!insightReady || pending} onClick={() => void analyze()}>运行推荐洞察包</button></div>}
        </aside>
      </div>
      {tagConfirm ? <dialog ref={tagDialog} className="confirm-overlay tag-confirm-overlay" aria-labelledby="tag-confirm-title" onCancel={() => setTagConfirm(false)} onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("textarea, button:not(:disabled)"));
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }}>
        <form className="confirm-dialog" onSubmit={(event) => {
          event.preventDefault();
          void send(selectionMessage(selectedTags, tagNote), selectedTags, !tagNote.trim()).then((sent) => { if (sent) setTagConfirm(false); });
        }}>
          <h2 id="tag-confirm-title">让智能体梳理所选标签</h2>
          <TagChips tags={selectedTags} />
          <label className="field-label">补充说明（可选）<textarea autoFocus rows={3} maxLength={Math.max(0, 2000 - selectionMessage(selectedTags).length - 8)} value={tagNote} onChange={(event) => setTagNote(event.target.value)} placeholder="例如：这些条件需要同时满足；具体阈值请逐项和我确认" /></label>
          <p>标签作为优先候选；未说明的筛选值和组合关系会继续向你确认。</p>
          {error ? <p className="tag-selection-notice" role="alert">{error}</p> : null}
          <div className="confirm-actions"><button type="button" disabled={pending} onClick={() => setTagConfirm(false)}>取消</button><button className="primary" disabled={!selectedTags.length || !!tagBlocked}>确认并梳理</button></div>
        </form>
      </dialog> : null}
      {deleteAllConfirm ? (
        <dialog
          ref={deleteAllDialog}
          onCancel={() => setDeleteAllConfirm(false)}
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
          aria-labelledby="delete-all-threads-title"
        >
          <div className="confirm-dialog">
            <h2 id="delete-all-threads-title">永久删除全部已归档会话？</h2>
            <p>
              将删除 {history.length} 个已归档会话，对话、圈选方案和处理记录都无法恢复。
            </p>
            <div className="confirm-actions">
              <button autoFocus onClick={() => setDeleteAllConfirm(false)}>
                取消
              </button>
              <button
                className="danger-button"
                disabled={pending}
                onClick={() => deleteAllArchivedThreads()}
              >
                永久删除
              </button>
            </div>
          </div>
        </dialog>
      ) : null}
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
  return (
    <ListboxSelect
      ariaLabel="当前标签库"
      listboxLabel="选择标签库"
      placeholder="选择标签库"
      placement="top"
      triggerClassName="library-select-trigger--context"
      leading={<LibraryGlyph />}
      disabled={disabled}
      value={value === "" ? "" : String(value)}
      onChange={(libraryId) => onChange(Number(libraryId))}
      options={libraries.map((item) => ({
        value: String(item.libraryId),
        label: item.libraryName,
      }))}
    />
  );
}

function LibraryGlyph() {
  return (
    <svg
      className="composer-context-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20.4 13.2 13 20.6a2 2 0 0 1-2.8 0L3.4 13.8a2 2 0 0 1 0-2.8L10.8 3.6A2 2 0 0 1 12.2 3H19a2 2 0 0 1 2 2v6.8a2 2 0 0 1-.6 1.4Z" />
      <circle cx="16.2" cy="7.8" r="1.15" />
    </svg>
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
