package com.lqq.supportflow.model.infrastructure.security;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import com.lqq.supportflow.model.domain.ModelSecretPort;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;

@Component
public class ApiKeyCipher implements ModelSecretPort {

    private static final int NONCE_BYTES = 12;
    private final SecureRandom random = new SecureRandom();

    public String encrypt(String plaintext, String masterKeyBase64) {
        try {
            byte[] nonce = new byte[NONCE_BYTES];
            random.nextBytes(nonce);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, key(masterKeyBase64), new GCMParameterSpec(128, nonce));
            byte[] encrypted = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            byte[] payload = new byte[nonce.length + encrypted.length];
            System.arraycopy(nonce, 0, payload, 0, nonce.length);
            System.arraycopy(encrypted, 0, payload, nonce.length, encrypted.length);
            return Base64.getEncoder().encodeToString(payload);
        } catch (Exception exception) { throw new IllegalStateException("cannot encrypt model API key", exception); }
    }
    @Override public String encrypt(String plaintext) {
        String masterKey = System.getenv("MODEL_SECRET_MASTER_KEY");
        if (masterKey == null || masterKey.isBlank()) throw new IllegalStateException("MODEL_SECRET_MASTER_KEY is required");
        return encrypt(plaintext, masterKey);
    }

    public String decrypt(String ciphertext, String masterKeyBase64) {
        try {
            byte[] payload = Base64.getDecoder().decode(ciphertext);
            byte[] nonce = java.util.Arrays.copyOfRange(payload, 0, NONCE_BYTES);
            byte[] encrypted = java.util.Arrays.copyOfRange(payload, NONCE_BYTES, payload.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(masterKeyBase64), new GCMParameterSpec(128, nonce));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception exception) { throw new IllegalArgumentException("cannot decrypt model API key", exception); }
    }

    private SecretKeySpec key(String masterKeyBase64) {
        byte[] bytes = Base64.getDecoder().decode(masterKeyBase64);
        if (bytes.length != 32) throw new IllegalArgumentException("MODEL_SECRET_MASTER_KEY must be a Base64-encoded 32-byte key");
        return new SecretKeySpec(bytes, "AES");
    }
}
