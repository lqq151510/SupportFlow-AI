"""模型 API Key 的 AES-GCM 加密。

对齐 AGENTS.md §4 与 PLAN.md §6：

- 主密钥**只**来自 ``MODEL_SECRET_MASTER_KEY`` 环境变量，要求是 32 字节的 base64；
- 主密钥缺失或形态不对时**直接失败**，绝不退化为存明文（fail closed）；
- 密文自带版本前缀，便于将来轮换算法时区分新旧数据；
- 解密使用 AEAD 的附加数据绑定用途，密文被换到别处或遭篡改都会解密失败。
"""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from supportflow.shared.config import Settings, get_settings
from supportflow.shared.errors import ModelConfigInvalid

MASTER_KEY_ENV = "MODEL_SECRET_MASTER_KEY"

#: AES-256。
MASTER_KEY_BYTES = 32
NONCE_BYTES = 12

#: 密文版本。轮换算法时新增版本并保留旧版本解密分支，避免历史数据不可读。
CIPHERTEXT_VERSION = "v1"

#: 附加数据：把密文绑定到「模型配置的密钥」这一用途，防止跨用途搬运。
_AAD = b"supportflow.model-config.api-key.v1"

GENERATE_KEY_HINT = (
    f"请用 `openssl rand -base64 32` 生成主密钥并写入环境变量 {MASTER_KEY_ENV}，"
    "例如 `export MODEL_SECRET_MASTER_KEY=\"$(openssl rand -base64 32)\"`。"
)


def decode_master_key(master_key: str) -> bytes:
    """把 base64 主密钥解码为 32 字节。形态不对即失败。"""
    candidate = master_key.strip()
    if not candidate:
        raise ModelConfigInvalid(f"未配置 {MASTER_KEY_ENV}。{GENERATE_KEY_HINT}")

    # 同时接受标准与 URL-safe 变体，并容忍缺失的补齐符。
    normalized = candidate.replace("-", "+").replace("_", "/")
    normalized += "=" * (-len(normalized) % 4)
    try:
        raw = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ModelConfigInvalid(
            f"{MASTER_KEY_ENV} 不是合法的 base64。{GENERATE_KEY_HINT}"
        ) from exc

    if len(raw) != MASTER_KEY_BYTES:
        raise ModelConfigInvalid(
            f"{MASTER_KEY_ENV} 解码后应为 {MASTER_KEY_BYTES} 字节，实际为 {len(raw)} 字节。"
            f"{GENERATE_KEY_HINT}"
        )
    return raw


class AesGcmSecretCipher:
    """AES-256-GCM 实现。同一实例可重复加密（每次使用独立随机 nonce）。"""

    def __init__(self, master_key: str) -> None:
        self._aesgcm = AESGCM(decode_master_key(master_key))

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ModelConfigInvalid("API Key 不能为空")
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), _AAD)
        return ".".join(
            (
                CIPHERTEXT_VERSION,
                base64.b64encode(nonce).decode("ascii"),
                base64.b64encode(sealed).decode("ascii"),
            )
        )

    def decrypt(self, ciphertext: str) -> str:
        version, _, rest = ciphertext.partition(".")
        if not rest:
            raise ModelConfigInvalid("密钥密文格式不正确")
        if version != CIPHERTEXT_VERSION:
            raise ModelConfigInvalid(f"不支持的密钥密文版本：{version!r}")

        nonce_b64, _, sealed_b64 = rest.partition(".")
        if not sealed_b64:
            raise ModelConfigInvalid("密钥密文格式不正确")
        try:
            nonce = base64.b64decode(nonce_b64, validate=True)
            sealed = base64.b64decode(sealed_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ModelConfigInvalid("密钥密文不是合法的 base64") from exc

        try:
            return self._aesgcm.decrypt(nonce, sealed, _AAD).decode("utf-8")
        except InvalidTag as exc:
            # 主密钥不匹配或密文被篡改。绝不返回可疑明文。
            raise ModelConfigInvalid(
                f"密钥密文校验失败：主密钥不匹配或密文已被篡改（{MASTER_KEY_ENV} 是否变过？）"
            ) from exc


def cipher_from_settings(settings: Settings | None = None) -> AesGcmSecretCipher:
    cfg = settings or get_settings()
    return AesGcmSecretCipher(cfg.model_secret_master_key)
