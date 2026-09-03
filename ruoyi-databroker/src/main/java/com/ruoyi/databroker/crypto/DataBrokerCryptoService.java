package com.ruoyi.databroker.crypto;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import javax.annotation.PostConstruct;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.databroker.config.DataBrokerProperties;

@Service
public class DataBrokerCryptoService {

    private static final String ALGORITHM = "AES";
    private static final String TRANSFORMATION = "AES/GCM/NoPadding";
    private static final int GCM_IV_LENGTH = 12;
    private static final int GCM_TAG_LENGTH = 128;
    /** application.yml 中 databroker.crypto.secret 的默认占位值 */
    private static final String DEFAULT_PLACEHOLDER_SECRET = "change-me-32-bytes-secret-key";

    @Autowired
    private DataBrokerProperties properties;

    private SecretKeySpec keySpec;

    @PostConstruct
    public void init() {
        String secret = properties.getCrypto().getSecret();
        // 密钥公开/缺失时库中密码密文可被解密，启动即失败强制部署方配置
        if (secret == null || secret.isEmpty()) {
            throw new IllegalStateException("databroker.crypto.secret 未配置，请设置环境变量 DATABROKER_CRYPTO_SECRET 或在 application.yml 中配置");
        }
        if (DEFAULT_PLACEHOLDER_SECRET.equals(secret)) {
            throw new IllegalStateException("databroker.crypto.secret 仍为默认占位值，请更换为自定义密钥（环境变量 DATABROKER_CRYPTO_SECRET）");
        }
        // Ensure key is 16 bytes (128-bit) for AES
        byte[] keyBytes = new byte[16];
        byte[] secretBytes = secret.getBytes(StandardCharsets.UTF_8);
        System.arraycopy(secretBytes, 0, keyBytes, 0, Math.min(secretBytes.length, 16));
        this.keySpec = new SecretKeySpec(keyBytes, ALGORITHM);
    }

    public String encrypt(String plainText) {
        if (plainText == null || plainText.isEmpty()) {
            return "";
        }
        try {
            byte[] iv = new byte[GCM_IV_LENGTH];
            SecureRandom random = new SecureRandom();
            random.nextBytes(iv);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, spec);

            byte[] cipherText = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            byte[] combined = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(cipherText, 0, combined, iv.length, cipherText.length);

            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw new RuntimeException("Password encryption failed", e);
        }
    }

    public String decrypt(String cipherText) {
        if (cipherText == null || cipherText.isEmpty()) {
            return "";
        }
        try {
            byte[] combined = Base64.getDecoder().decode(cipherText);
            byte[] iv = new byte[GCM_IV_LENGTH];
            byte[] encrypted = new byte[combined.length - GCM_IV_LENGTH];
            System.arraycopy(combined, 0, iv, 0, GCM_IV_LENGTH);
            System.arraycopy(combined, GCM_IV_LENGTH, encrypted, 0, encrypted.length);

            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            GCMParameterSpec spec = new GCMParameterSpec(GCM_TAG_LENGTH, iv);
            cipher.init(Cipher.DECRYPT_MODE, keySpec, spec);

            byte[] plainText = cipher.doFinal(encrypted);
            return new String(plainText, StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new RuntimeException("Password decryption failed", e);
        }
    }

    /**
     * Mask sensitive fields in JSON string for log storage.
     */
    public String maskSensitive(String json) {
        if (json == null || json.isEmpty()) {
            return json;
        }
        return json
            .replaceAll("\"password\"\\s*:\\s*\"[^\"]*\"", "\"password\":\"******\"")
            .replaceAll("\"passwordCipher\"\\s*:\\s*\"[^\"]*\"", "\"passwordCipher\":\"******\"")
            .replaceAll("\"caCert\"\\s*:\\s*\"[^\"]*\"", "\"caCert\":\"******\"")
            .replaceAll("\"secret\"\\s*:\\s*\"[^\"]*\"", "\"secret\":\"******\"")
            .replaceAll("\"token\"\\s*:\\s*\"[^\"]*\"", "\"token\":\"******\"")
            .replaceAll("\"key\"\\s*:\\s*\"[^\"]*\"", "\"key\":\"******\"");
    }
}
