export const AGENT_BACK_MESSAGE = "tagpilot-agent:back";
export const DEFAULT_FROM = "/taglibrary/list";

export type WorkbenchContext = {
  libraryId?: number;
  libraryName?: string;
  from: string;
};

export function isSafeInternalPath(path: string | undefined | null): path is string {
  return Boolean(path && path.startsWith("/") && !path.startsWith("//") && !path.includes("://"));
}

export function parseWorkbenchQuery(search: string): WorkbenchContext {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const rawId = params.get("libraryId");
  const libraryId = rawId ? Number(rawId) : undefined;
  return {
    libraryId: Number.isFinite(libraryId) && libraryId! > 0 ? libraryId : undefined,
    libraryName: params.get("libraryName") || undefined,
    from: isSafeInternalPath(params.get("from")) ? params.get("from")! : DEFAULT_FROM,
  };
}

export function requestBackToWorkbench(from: string): void {
  const target = isSafeInternalPath(from) ? from : DEFAULT_FROM;
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ type: AGENT_BACK_MESSAGE, from: target }, window.location.origin);
    return;
  }
  window.location.assign(target);
}
