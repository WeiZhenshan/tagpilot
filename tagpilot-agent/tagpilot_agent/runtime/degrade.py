"""降级原因和兼容契约，进度只写入方案诊断。"""
import os
from tagpilot_agent.retrieval.semantic_client import SemanticRetrieveError


class Reason:
    TIMEOUT='timeout'; MEMORY='memory_limit'; MAX_TURNS='max_turns'; MAX_BUDGET='max_budget'
    TOOL_BUDGET='tool_budget'; QUEUE_TIMEOUT='queue_timeout'; GATEWAY='gateway'; RETRIEVAL='retrieval'


BUDGET_REASONS={Reason.TIMEOUT,Reason.MEMORY,Reason.MAX_TURNS,Reason.MAX_BUDGET,Reason.TOOL_BUDGET}
LEAN_REASONS=BUDGET_REASONS-{Reason.MEMORY}
MESSAGES={Reason.TIMEOUT:'处理时间较长，已保留已确认的条件',
          Reason.MEMORY:'运行资源不足，已保存进度，请手工编辑或稍后重试',
          Reason.MAX_TURNS:'本轮处理次数已达上限，已保留当前方案',
          Reason.MAX_BUDGET:'本轮模型预算已用完，已保留当前方案',
          Reason.TOOL_BUDGET:'本轮检索与核验预算已用完，已保留当前方案',
          Reason.QUEUE_TIMEOUT:'当前使用人数较多，排队已超时，请稍后重试',
          Reason.GATEWAY:'模型服务暂不可用，已保存进度，请稍后重试',
          Reason.RETRIEVAL:'标签检索服务暂不可用，已保存进度，请稍后重试'}


def progress(plan):
    return next((d for d in reversed((plan or {}).get('diagnostics',[])) if d.get('code')=='BUDGET_EXHAUSTED'),{})


def classify(ctx,exc=None,admitted=True):
    stop=ctx.stats.get('stop_reason')
    if isinstance(exc,SemanticRetrieveError):return Reason.RETRIEVAL
    if isinstance(exc,TimeoutError) and not admitted:return Reason.QUEUE_TIMEOUT
    # SDK 网关错误可能最后被 watchdog 超时中断，保留真正原因。
    if (stop==Reason.TIMEOUT or isinstance(exc,TimeoutError)) and not ctx.stats.get('tools') and ctx.stats.get('sdk_error'):
        return Reason.GATEWAY
    if stop in BUDGET_REASONS | {Reason.QUEUE_TIMEOUT,Reason.GATEWAY,Reason.RETRIEVAL}:return stop
    sdk={'error_max_turns':Reason.MAX_TURNS,'error_max_budget_usd':Reason.MAX_BUDGET}.get(ctx.stats.get('sdk_result'))
    if sdk:return sdk
    if ctx.stats.get('tool_budget_hit'):return Reason.TOOL_BUDGET
    if isinstance(exc,TimeoutError):return Reason.TIMEOUT
    if exc or ctx.stats.get('sdk_error'):return Reason.GATEWAY
    if ctx.stats.get('retrieval_unavailable'):return Reason.RETRIEVAL
    return None


def degraded_info(ctx,reason,level,kept,unresolved,attempt=0):
    resumable=reason!=Reason.MEMORY and attempt<=max(0,int(os.getenv('TAG_AGENT_MAX_DEGRADE_RESUMES','2')))
    message=MESSAGES[reason]
    if not resumable and reason!=Reason.MEMORY:message+='；建议拆分需求或手工编辑方案'
    return {'level':level,'reason':reason,'kept_clauses':kept,'unresolved_clause_ids':unresolved,
            'resumable':resumable,'resume_mode':'lean' if reason in LEAN_REASONS else 'manual' if reason==Reason.MEMORY else 'retry',
            'attempt':attempt,'user_message':message,'ops_alert':reason==Reason.MEMORY}
