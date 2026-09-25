"""测试隔离：进程级检索缓存不能跨用例泄漏。"""
import pytest

from tagpilot_agent.retrieval.cache import cards_cache, details_cache


@pytest.fixture(autouse=True)
def _clear_process_caches():
    cards_cache.data.clear()
    details_cache.data.clear()
    yield
    cards_cache.data.clear()
    details_cache.data.clear()
