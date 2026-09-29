"""只接收调用前的目的说明；不展示推理、编号或技术内容。"""
import re

FORBIDDEN = re.compile(r'find_tags|get_tag_details|find_capabilities|check_plan|submit_result|\bR\d+\b|\b\d{4,}\b|[{}]|\b(?:select|insert|update|delete|from|join|where|sql)\b|[a-zA-Z]+_\w+|\b(?:tag|clause|requirement)[ _-]?id\b', re.I)


def clean_narration(text):
    if not isinstance(text, str) or FORBIDDEN.search(text):
        return None
    # 英文术语较多的句子整条舍弃，前端仍有工具对象描述。
    letters = sum(c.isascii() and c.isalpha() for c in text)
    if letters / max(1, len(text)) > .25:
        return None
    text = re.sub(r'[*`#>~\[\]]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:60] or None


class NarrationEmitter:
    """SDK 0.1.50 会将一次回复拆成 Text 和 ToolUse 两条 AssistantMessage。"""
    def __init__(self):
        self.pending = []
        self.emitted = False

    def consume(self, ctx, message):
        from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, UserMessage, ResultMessage
        if ctx.accepted or isinstance(message, (UserMessage, ResultMessage)):
            self.pending.clear()
            self.emitted = False
            return
        if not isinstance(message, AssistantMessage):
            return
        self.pending.extend(b.text for b in message.content if isinstance(b, TextBlock))
        if not any(isinstance(b, ToolUseBlock) for b in message.content):
            return
        text = clean_narration(' '.join(self.pending))
        self.pending.clear()
        if text and not self.emitted:
            ctx.emit({'type': 'narration', 'text': text})
            self.emitted = True
