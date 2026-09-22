import { type ReactNode, useMemo } from "react";
import { AssistantRuntimeProvider, useLocalRuntime } from "@assistant-ui/react";
import { createRetrieveAdapter } from "./retrieveAdapter";

type RuntimeProviderProps = {
  libraryId?: number;
  children: ReactNode;
};

export function RuntimeProvider({ libraryId, children }: RuntimeProviderProps) {
  const adapter = useMemo(
    () => createRetrieveAdapter({ getLibraryId: () => libraryId }),
    [libraryId],
  );
  const runtime = useLocalRuntime(adapter);
  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>;
}
