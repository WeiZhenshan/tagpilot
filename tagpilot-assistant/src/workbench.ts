export const AGENT_BACK_MESSAGE = "tagpilot-agent:back";
export const AGENT_LOGOUT_MESSAGE = "tagpilot-agent:logout";
export const DEFAULT_FROM = "/taglibrary/list";

export type WorkbenchContext = {
  libraryId?: number;
  libraryName?: string;
  groupId?: number;
  from: string;
};

export function isSafeInternalPath(path: string | undefined | null): path is string {
  return Boolean(path && path.startsWith("/") && !path.startsWith("//") && !path.includes("://"));
}

export function parseWorkbenchQuery(search: string): WorkbenchContext {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const rawId = params.get("libraryId");
  const libraryId = rawId ? Number(rawId) : undefined;
  const groupId = Number(params.get("groupId"));
  return {
    libraryId: Number.isFinite(libraryId) && libraryId! > 0 ? libraryId : undefined,
    libraryName: params.get("libraryName") || undefined,
    groupId: Number.isSafeInteger(groupId) && groupId > 0 ? groupId : undefined,
    from: normalizeBackPath(params.get("from")),
  };
}

export function requestBackToWorkbench(from: string): void {
  const target = normalizeBackPath(from);
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ type: AGENT_BACK_MESSAGE, from: target }, window.location.origin);
    return;
  }
  window.location.assign(target);
}

export function normalizeBackPath(from: string | null | undefined): string {
  return isSafeInternalPath(from) ? from.replace(/^\/objectgroup\/list(?=[?#]|$)/, "/objectgroup/group") : DEFAULT_FROM;
}

export function requestLogout(): void {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(
      { type: AGENT_LOGOUT_MESSAGE },
      window.location.origin
    );
    return;
  }
  window.location.assign("/login");
}
