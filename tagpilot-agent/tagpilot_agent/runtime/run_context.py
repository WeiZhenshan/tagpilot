from dataclasses import dataclass, field
from typing import Callable, Any
import asyncio
import time
from tagpilot_agent.retrieval.cache import eligible_hash

@dataclass
class RunContext:
    request: dict
    retriever: Any
    emit: Callable = lambda e: None
    cancelled: Callable = lambda: False
    tags: dict = field(default_factory=dict)
    codes: list = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)
    details_loaded: set = field(default_factory=set)
    searches: dict = field(default_factory=dict)
    stats: dict = field(default_factory=lambda: {'tools':0,'deep':0,'details':0,'submit_rejections':0,'llm_turns':0})
    best_plan: dict | None = None
    best_errors: int = 10000
    accepted: dict | None = None
    started: float = field(default_factory=time.monotonic)
    submitted: asyncio.Event = field(default_factory=asyncio.Event)
    intent_emitted: bool = False
    last_diagnostic: str = ''
    diagnostic_repeats: int = 0

    @property
    def eligible(self):return set(self.request['eligible_tag_ids'])
    @property
    def cache_scope(self):
        return (getattr(self.retriever,'base_url',''),self.request['library_id'],self.request['build_id'],self.request['artifact_hash'],eligible_hash(self.eligible))
