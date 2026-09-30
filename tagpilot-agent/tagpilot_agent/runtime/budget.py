"""每次运行共享预算；重试沿用剩余时间，精简模式不扩大已有上限。"""
from dataclasses import dataclass
import os
import time


@dataclass
class Budget:
    soft: float
    hard: float
    max_turns: int
    max_tools: int
    max_deep: int
    max_details: int
    converge_ratio: float = .65
    salvage_margin: float = 12.

    @classmethod
    def from_env(cls, lean=False, skill=False):
        hard=max(.1,float(os.getenv('TAG_AGENT_HARD_TIMEOUT','90')))
        soft=max(0.,float(os.getenv('TAG_AGENT_SOFT_TIMEOUT','40')))
        turns=max(1,int(os.getenv('TAG_AGENT_MAX_TURNS','16')))
        if lean:
            hard=min(hard,max(.1,float(os.getenv('TAG_AGENT_LEAN_HARD','60'))))
            soft=min(soft,max(0.,float(os.getenv('TAG_AGENT_LEAN_SOFT','25'))))
            turns=max(1,turns//2)
        # 技能运行是单次分析：读技能资料、按需配图需要更多墙钟时间，且没有圈选的收敛语义；
        # 圈选流程的 hard/soft 保持不变。
        if skill:
            hard=max(hard,max(.1,float(os.getenv('TAG_AGENT_SKILL_HARD_TIMEOUT','150'))))
        return cls(min(soft,hard),hard,turns,max(1,int(os.getenv('TAG_AGENT_MAX_TOOLS','16'))),
                   0 if lean else max(0,int(os.getenv('TAG_AGENT_MAX_DEEP','4'))),
                   max(1,int(os.getenv('TAG_AGENT_MAX_DETAILS','6'))),
                   min(1.,max(.01,float(os.getenv('TAG_AGENT_CONVERGE_RATIO','.65')))),
                   max(0.,float(os.getenv('TAG_AGENT_SALVAGE_MARGIN','12'))))

    def elapsed(self,ctx):return max(0.,time.monotonic()-ctx.started)

    def ratio(self,ctx):
        stats=ctx.stats
        return max(self.elapsed(ctx)/self.hard,stats.get('tools',0)/self.max_tools,
                   stats.get('deep',0)/self.max_deep if self.max_deep else 0,
                   max(stats.get('details',0),stats.get('evidence_requests',0))/self.max_details,
                   stats.get('llm_turns',0)/self.max_turns)

    def converging(self,ctx):return self.elapsed(ctx)>=self.soft or self.ratio(ctx)>=self.converge_ratio

    def salvage_at(self):return self.hard-min(self.salvage_margin,self.hard*.2)

    def snapshot(self,ctx):
        return {'remaining_s':round(max(0.,self.hard-self.elapsed(ctx)),1),
                'remaining_tools':max(0,self.max_tools-ctx.stats.get('tools',0)),
                'mode':'converge' if self.converging(ctx) else 'normal'}

    def announce(self,ctx):
        if self.converging(ctx) and 'converging_at' not in ctx.stats:
            ctx.stats['converging_at']=round(self.elapsed(ctx),3)
            ctx.emit({'type':'budget.converging','message':'正在整理已确认的条件'})
