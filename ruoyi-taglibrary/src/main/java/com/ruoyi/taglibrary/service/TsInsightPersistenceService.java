package com.ruoyi.taglibrary.service;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.utils.SecurityUtils;
import com.ruoyi.common.exception.ServiceException;
import com.ruoyi.databroker.crypto.DataBrokerCryptoService;
import com.ruoyi.taglibrary.mapper.TsInsightMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;
/** 报告保存与成功审计在短事务中提交；失败审计不保留查询或客户信息。 */
@Service
public class TsInsightPersistenceService {
 @Autowired private TsAgentWorkbenchService workbench;
 @Autowired private TsInsightMapper mapper;
 @Autowired private DataBrokerCryptoService crypto;
 @Autowired private ObjectMapper json;
 @Transactional public void success(String thread,Map<String,Object> request,Map<String,Object> report,Long library,Long revision,String hash,long elapsed){
  workbench.saveInsight(thread,request,report);
  try{mapper.run(String.valueOf(report.get("run_id")),library,thread,SecurityUtils.getUserId(),revision,hash,"L4".equals(report.get("level"))?"BLOCKED":"L2".equals(report.get("level"))?"PARTIAL":"COMPLETED",crypto.encrypt(json.writeValueAsString(report)),elapsed);}
  catch(java.io.IOException e){throw new ServiceException("洞察审计保存失败");}
 }
 @Transactional(propagation=Propagation.REQUIRES_NEW) public void failure(String run,Long library,String thread,Long revision,String hash,long elapsed){
  mapper.run(run,library,thread,SecurityUtils.getUserId(),revision,hash,"FAILED",crypto.encrypt("{\"message\":\"洞察未完成，未保存报告\"}"),elapsed);
 }
}
