"""本地白名单遥测；不记录模型消息、凭据或用户原话。"""
from contextlib import contextmanager
import time

ALLOWED={'tool','duration_ms','status','count','depth','cli_peak_rss_mb','llm_turns','input_tokens','output_tokens'}

@contextmanager
def span(emit,name,**attributes):
    started=time.monotonic();status='ok'
    try:yield
    except BaseException:
        status='error';raise
    finally:
        emit({'type':'telemetry.span','name':name,**{k:v for k,v in attributes.items() if k in ALLOWED},
              'duration_ms':round((time.monotonic()-started)*1000),'status':status})
