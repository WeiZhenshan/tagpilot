import type { ChatModelAdapter } from "@assistant-ui/react";
import { retrieveSemantic, type RetrieveResult } from "./api";
import { formatRetrieveText, lastUserText } from "./formatResult";

export type RetrieveAdapterOptions = {
  getLibraryId: () => number | undefined;
};

export function createRetrieveAdapter(options: RetrieveAdapterOptions): ChatModelAdapter {
  return {
    async run({ messages, abortSignal }) {
      const libraryId = options.getLibraryId();
      if (!libraryId) {
        throw new Error("请先选择标签库，再描述要查找的客群条件。");
      }
      const requirement = lastUserText(messages);
      if (!requirement) {
        throw new Error("请输入自然语言查询条件。");
      }
      const response = await retrieveSemantic(libraryId, requirement, abortSignal);
      const result: RetrieveResult = response.data || {};
      return {
        content: [
          { type: "text", text: formatRetrieveText(result) },
          { type: "data", name: "tag-suggestion", data: JSON.parse(JSON.stringify(result)) as RetrieveResult },
        ],
      };
    },
  };
}
