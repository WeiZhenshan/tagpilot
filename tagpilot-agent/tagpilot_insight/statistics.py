"""比例与结构标准化。Wilson区间；多格基准使用Bonferroni同时区间的加权包络。"""
from math import sqrt
from statistics import NormalDist


def wilson(successes: int, n: int, alpha: float = .05) -> tuple[float,float]:
    if not 0 <= successes <= n or n <= 0 or not 0 < alpha < 1:
        raise ValueError("比例样本非法")
    z=NormalDist().inv_cdf(1-alpha/2);p=successes/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    margin=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return max(0.,center-margin)*100,min(100.,center+margin)*100


def standardize(cohort, benchmark, *, min_sample=30, mode="aum_risk"):
    """输入仅为Java已经抑制后的格聚合。二维→AUM→风险；仍不足就不比较。"""
    def collapse(rows, axis):
        out={}
        for r in rows:
            if r.status != "AVAILABLE" or r.n is None or r.holders is None:
                raise ValueError("覆盖率格缺失或已抑制，不能默认为零")
            if "unknown" in r.dimensions:
                raise ValueError("分层或风险未知，不能比较")
            valid_n=r.n-(r.missing or 0)
            if valid_n <= 0 or r.holders > valid_n:
                raise ValueError("持有标志有效样本不足")
            key=tuple(r.dimensions) if axis is None else (r.dimensions[axis],)
            n,s=out.get(key,(0,0));out[key]=(n+valid_n,s+r.holders)
        return out
    if not cohort or not benchmark or any(len(r.dimensions)!=2 for r in [*cohort,*benchmark]):
        raise ValueError("标准化缺少AUM×风险聚合")
    axes=[(None,"AUM×风险"),(0,"AUM"),(1,"风险")] if mode=="aum_risk" else [(0,"AUM")] if mode=="aum" else [(1,"风险")] if mode=="risk" else []
    for axis,label in axes:
        c=collapse(cohort,axis);b=collapse(benchmark,axis)
        if any(n<min_sample or k not in b or b[k][0]<min_sample for k,(n,_) in c.items()):continue
        total=sum(n for n,_ in c.values());weights={k:n/total for k,(n,_) in c.items()}
        rate=sum(weights[k]*b[k][1]/b[k][0]*100 for k in c)
        # 此区间比独立正态近似保守，不把小样本标准误视为零。
        intervals={k:wilson(b[k][1],b[k][0],.05/len(c)) for k in c}
        baseline_ci=tuple(sum(weights[k]*intervals[k][i] for k in c) for i in (0,1))
        holders=sum(s for _,s in c.values());cohort_rate=holders/total*100
        cohort_ci=wilson(holders,total)
        return dict(cohort=c,benchmark={k:b[k] for k in c},weights=weights,rate=rate,cohort_rate=cohort_rate,
                    cohort_ci=cohort_ci,benchmark_ci=baseline_ci,gap=rate-cohort_rate,
                    nonoverlapping=cohort_ci[1]<baseline_ci[0],mode=label,
                    fallback=label!="AUM×风险",sample=total,baseline_sample=sum(b[k][0] for k in c))
    raise ValueError("单维回退后样本仍不足，比较已抑制")
