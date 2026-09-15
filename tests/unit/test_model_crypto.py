"""API Key 加解密单测。

对齐 AGENTS.md §4：主密钥只来自环境变量、格式必须严格、密文被篡改或主密钥不匹配时
**必须失败**而不是返回可疑明文。这里用测试专用主密钥，不涉及任何真实密钥。
"""

from __future__ import annotations

import base64
import os

import pytest

from supportflow.model.infrastructure.crypto import (
    CIPHERTEXT_VERSION,
    MASTER_KEY_ENV,
    AesGcmSecretCipher,
    cipher_from_settings,
    decode_master_key,
)
from supportflow.shared.config import Settings
from supportflow.shared.errors import ModelConfigInvalid


def _key(label: str) -> str:
    """构造恰好 32 字节的测试主密钥。

    手工写常量很容易写成 33 字节然后把「测试数据不对」误判成实现缺陷，
    因此这里用填充 + 截断保证长度，并由下面的自证用例守住。
    """
    return base64.b64encode(label.encode("utf-8").ljust(32, b".")[:32]).decode("ascii")


KEY_A = _key("unit-test-key-a")
KEY_B = _key("unit-test-key-b")
PLAINTEXT = "sk-test-1234567890-abcdefghijklmnop"


def test_test_keys_are_thirty_two_bytes() -> None:
    """自证测试数据本身有效，避免把「长度不对」误判成实现缺陷。"""
    assert len(decode_master_key(KEY_A)) == 32
    assert len(decode_master_key(KEY_B)) == 32


def test_round_trip_returns_original_plaintext() -> None:
    cipher = AesGcmSecretCipher(KEY_A)
    ciphertext = cipher.encrypt(PLAINTEXT)
    assert ciphertext != PLAINTEXT
    assert PLAINTEXT not in ciphertext
    assert cipher.decrypt(ciphertext) == PLAINTEXT


def test_ciphertext_is_versioned_and_has_three_parts() -> None:
    """带版本前缀，将来轮换算法才能区分新旧数据。"""
    ciphertext = AesGcmSecretCipher(KEY_A).encrypt(PLAINTEXT)
    version, nonce, sealed = ciphertext.split(".")
    assert version == CIPHERTEXT_VERSION
    assert len(base64.b64decode(nonce)) == 12
    assert base64.b64decode(sealed)


def test_same_plaintext_encrypts_differently_each_time() -> None:
    """每次使用独立随机 nonce，相同明文不得产出相同密文。"""
    cipher = AesGcmSecretCipher(KEY_A)
    assert cipher.encrypt(PLAINTEXT) != cipher.encrypt(PLAINTEXT)


def test_tampered_ciphertext_is_rejected() -> None:
    cipher = AesGcmSecretCipher(KEY_A)
    version, nonce, sealed = cipher.encrypt(PLAINTEXT).split(".")
    raw = bytearray(base64.b64decode(sealed))
    raw[0] ^= 0x01  # 翻转一位
    tampered = ".".join((version, nonce, base64.b64encode(bytes(raw)).decode()))
    with pytest.raises(ModelConfigInvalid) as excinfo:
        cipher.decrypt(tampered)
    assert "篡改" in str(excinfo.value) or "校验失败" in str(excinfo.value)


def test_decrypt_with_wrong_master_key_is_rejected() -> None:
    ciphertext = AesGcmSecretCipher(KEY_A).encrypt(PLAINTEXT)
    with pytest.raises(ModelConfigInvalid):
        AesGcmSecretCipher(KEY_B).decrypt(ciphertext)


def test_empty_master_key_fails_with_actionable_hint() -> None:
    with pytest.raises(ModelConfigInvalid) as excinfo:
        AesGcmSecretCipher("")
    assert MASTER_KEY_ENV in str(excinfo.value)
    assert "openssl rand -base64 32" in str(excinfo.value)


def test_non_base64_master_key_is_rejected() -> None:
    with pytest.raises(ModelConfigInvalid):
        AesGcmSecretCipher("not base64 at all!!")


def test_wrong_length_master_key_is_rejected() -> None:
    short = base64.b64encode(b"only-sixteen-by").decode()
    with pytest.raises(ModelConfigInvalid) as excinfo:
        decode_master_key(short)
    assert "32" in str(excinfo.value)


def test_url_safe_base64_master_key_is_accepted() -> None:
    """openssl 与各类工具产出的 base64 变体都应可用，但长度仍须为 32 字节。"""
    raw = os.urandom(32)
    standard = base64.b64encode(raw).decode()
    urlsafe = base64.urlsafe_b64encode(raw).decode()
    assert decode_master_key(standard) == decode_master_key(urlsafe) == raw


@pytest.mark.parametrize(
    "broken",
    [
        "v2.AAAA.BBBB",
        "v1.AAAA",
        "no-separator-at-all",
        "v1.!!!!.????",
    ],
)
def test_malformed_ciphertext_is_rejected(broken: str) -> None:
    with pytest.raises(ModelConfigInvalid):
        AesGcmSecretCipher(KEY_A).decrypt(broken)


def test_empty_plaintext_is_rejected() -> None:
    with pytest.raises(ModelConfigInvalid):
        AesGcmSecretCipher(KEY_A).encrypt("")


def test_cipher_from_settings_reads_the_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """主密钥只能来自配置（即环境变量），不提供任何别的来源。"""
    settings = Settings(model_secret_master_key=KEY_A)
    ciphertext = cipher_from_settings(settings).encrypt(PLAINTEXT)
    assert cipher_from_settings(settings).decrypt(ciphertext) == PLAINTEXT

    monkeypatch.delenv(MASTER_KEY_ENV, raising=False)
    with pytest.raises(ModelConfigInvalid):
        cipher_from_settings(Settings(model_secret_master_key=""))
