package com.ruoyi.taglibrary.service;

import java.util.Iterator;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Lazy;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

/** 服务端轮询 RUNNING 会话，驱动 Java 分析管道与 Python 编排同步。 */
@Service
public class TsAgentRunSyncService {
    private static final Logger log = LoggerFactory.getLogger(TsAgentRunSyncService.class);
    private final Set<String> active = ConcurrentHashMap.newKeySet();
    @Autowired @Lazy private TsAgentWorkbenchService workbench;
    @Value("${taglibrary.agent.sync.enabled:true}")
    private boolean enabled;

    public void track(String threadId) {
        if (threadId != null && !threadId.isEmpty()) active.add(threadId);
    }

    public void untrack(String threadId) {
        if (threadId != null) active.remove(threadId);
    }

    public boolean tracked(String threadId) {
        return active.contains(threadId);
    }

    @Scheduled(fixedDelayString = "${taglibrary.agent.sync.interval-ms:2000}")
    public void pollActiveThreads() {
        if (!enabled || active.isEmpty()) return;
        for (Iterator<String> it = active.iterator(); it.hasNext();) {
            String threadId = it.next();
            try {
                if (!workbench.syncBackground(threadId)) it.remove();
            } catch (Exception e) {
                log.warn("智能体后台同步失败 thread={}: {}", threadId, e.getMessage());
            }
        }
    }
}
