"""内部只读语义客户端。身份/资格/版本由 Java 注入，不接受模型覆盖。"""
import time
import httpx

class SemanticRetrieveError(Exception):
    def __init__(self,status_code,detail):
        super().__init__(detail);self.status_code=status_code;self.detail=detail

class SemanticRetrieveClient:
    def __init__(self,base_url,token,library_id,build_id,timeout=30):
        self.base_url=base_url.rstrip('/');self.token=token;self.library_id=library_id;self.build_id=build_id;self.timeout=timeout

    def request(self,path,requirement,eligible,**fields):
        payload={'requirement':requirement[:500] or '标签详情','library_id':self.library_id,'build_id':self.build_id,'eligible_tag_ids':sorted(eligible),**fields}
        for attempt in range(2):
            try:
                r=httpx.post(self.base_url+path,json=payload,headers={'authorization':'Bearer '+self.token},timeout=self.timeout)
                if r.status_code in {429,502,503,504} and attempt==0:time.sleep(.3);continue
                if r.status_code>=400:raise SemanticRetrieveError(r.status_code,'语义服务暂不可用' if r.status_code>=500 else '语义服务拒绝请求')
                return r.json()
            except (httpx.TimeoutException,httpx.NetworkError) as exc:
                if attempt:raise SemanticRetrieveError(503,'语义服务暂不可用') from exc
        raise SemanticRetrieveError(503,'语义服务暂不可用')

    def retrieve(self,requirement,eligible_tag_ids,k=8,mode='deep'):
        return self.request('/retrieve',requirement,eligible_tag_ids,k=k,mode=mode)
    def retrieve_batch(self,queries,eligible,k=8,mode='deep'):
        return self.request('/retrieve_batch',queries[0],eligible,queries=queries,k=k,mode=mode)['results']
    def lookup(self,requirement,eligible,k=8):
        return self.request('/lookup',requirement,eligible,k=k)
    def evidence(self,tag_ids,requirement,eligible,value_query=None,max_values=None):
        return self.request('/evidence',requirement,eligible,tag_ids=tag_ids,value_query=value_query,max_values=max_values)
    def capabilities(self,requirement,eligible,capability_ids=None):
        return self.request('/capabilities',requirement,eligible,capability_ids=capability_ids or [])
