package com.ruoyi.taglibrary.service;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class TsAgentRunSyncServiceTest {
    @Mock TsAgentWorkbenchService workbench;
    @InjectMocks TsAgentRunSyncService service;

    @org.junit.jupiter.api.BeforeEach void enable() {
        ReflectionTestUtils.setField(service,"enabled",true);
    }

    @Test void pollRemovesThreadWhenBackgroundSyncFinishes() {
        service.track("t1");
        when(workbench.syncBackground("t1")).thenReturn(false);
        service.pollActiveThreads();
        assertFalse(service.tracked("t1"));
    }

    @Test void pollKeepsThreadWhileRunStillActive() {
        service.track("t2");
        when(workbench.syncBackground("t2")).thenReturn(true);
        service.pollActiveThreads();
        assertTrue(service.tracked("t2"));
    }
}
