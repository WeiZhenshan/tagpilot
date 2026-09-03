package com.ruoyi.databroker.crypto;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import com.ruoyi.databroker.config.DataBrokerProperties;

/**
 * 数据源密码加解密 Service 单元测试（纯Mockito，不起Spring上下文）
 *
 * @author ruoyi
 */
@ExtendWith(MockitoExtension.class)
class DataBrokerCryptoServiceTest {

    @Mock
    private DataBrokerProperties properties;

    @InjectMocks
    private DataBrokerCryptoService cryptoService;

    private DataBrokerProperties.Crypto newCrypto(String secret) {
        DataBrokerProperties.Crypto crypto = new DataBrokerProperties.Crypto();
        crypto.setSecret(secret);
        return crypto;
    }

    @Test
    void initRejectsDefaultPlaceholderSecret() {
        when(properties.getCrypto()).thenReturn(newCrypto("change-me-32-bytes-secret-key"));
        IllegalStateException e = assertThrows(IllegalStateException.class, () -> cryptoService.init());
        assertTrue(e.getMessage().contains("默认占位值"));
    }

    @Test
    void initRejectsNullSecret() {
        when(properties.getCrypto()).thenReturn(newCrypto(null));
        IllegalStateException e = assertThrows(IllegalStateException.class, () -> cryptoService.init());
        assertTrue(e.getMessage().contains("未配置"));
    }

    @Test
    void initRejectsEmptySecret() {
        when(properties.getCrypto()).thenReturn(newCrypto(""));
        assertThrows(IllegalStateException.class, () -> cryptoService.init());
    }

    @Test
    void initWithCustomSecretAllowsEncryptDecryptRoundTrip() {
        when(properties.getCrypto()).thenReturn(newCrypto("custom-32bytes-secret-0123456789ab"));
        assertDoesNotThrow(() -> cryptoService.init());
        String cipher = cryptoService.encrypt("数据源密码");
        assertEquals("数据源密码", cryptoService.decrypt(cipher));
    }
}
