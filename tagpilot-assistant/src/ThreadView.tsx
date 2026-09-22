import { ComposerPrimitive, MessagePrimitive, ThreadPrimitive } from "@assistant-ui/react";
import type { RetrieveResult } from "./api";
import { SuggestTagsCard } from "./SuggestTagsCard";

function messageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (typeof part === "string") return part;
      if (part && typeof part === "object" && "type" in part && part.type === "text") {
        return String((part as { text?: string }).text || "");
      }
      return "";
    })
    .join("\n");
}

function suggestResult(content: unknown): RetrieveResult | null {
  if (!Array.isArray(content)) return null;
  for (const part of content) {
    if (!part || typeof part !== "object") continue;
    const item = part as { type?: string; name?: string; data?: RetrieveResult };
    if (item.type === "data" && item.name === "tag-suggestion" && item.data) {
      return item.data;
    }
  }
  return null;
}

export function ThreadView({ disabled, placeholder }: { disabled: boolean; placeholder: string }) {
  return (
    <ThreadPrimitive.Root className="thread">
      <ThreadPrimitive.Viewport className="thread-viewport">
        <ThreadPrimitive.Empty>
          <div className="thread-empty">
            <h2>用自然语言查找已发布标签</h2>
            <p>智能体只在当前角色可用的已发布标签中建议，并通过 DSL 门禁。结果必须由你确认，不会自动圈客。</p>
          </div>
        </ThreadPrimitive.Empty>
        <ThreadPrimitive.Messages>
          {({ message }) => {
            if (message.role === "user") {
              return (
                <MessagePrimitive.Root className="msg msg-user">
                  <div className="msg-bubble">{messageText(message.content)}</div>
                </MessagePrimitive.Root>
              );
            }
            const suggestion = suggestResult(message.content);
            return (
              <MessagePrimitive.Root className="msg msg-assistant">
                <div className="msg-bubble">
                  <pre>{messageText(message.content)}</pre>
                  {suggestion ? <SuggestTagsCard result={suggestion} /> : null}
                </div>
              </MessagePrimitive.Root>
            );
          }}
        </ThreadPrimitive.Messages>
      </ThreadPrimitive.Viewport>
      <ComposerPrimitive.Root className="composer">
        <ComposerPrimitive.Input className="composer-input" rows={3} placeholder={placeholder} disabled={disabled} />
        <ComposerPrimitive.Send className="composer-send" disabled={disabled}>
          查询标签
        </ComposerPrimitive.Send>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  );
}
