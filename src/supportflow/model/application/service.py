"""模型配置用例：创建、更新、启用与连接测试。

三条不可让步的规则：

1. **明文 Key 只活在这个方法的栈上**：进入时立刻加密，之后只流转密文。
   任何返回值都不含明文，``ModelConfig`` 领域模型里根本没有这个字段。
2. **真实模式失败不降级**：连接测试如实报告失败原因，不返回 Mock 结果。
3. **启用互斥**：同类能力同时只有一个启用配置，由部分唯一索引兜底。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from uuid import UUID

from supportflow.identity.domain.models import Principal
from supportflow.model.domain.models import (
    ConnectionTestResult,
    ModelCapability,
    ModelConfig,
    ModelConfigUpdate,
    ModelProtocol,
    NewModelConfig,
    ResolvedChatConfig,
    ResolvedEmbeddingConfig,
)
from supportflow.model.domain.ports import ModelConfigRepositoryPort, SecretCipherPort
from supportflow.model.infrastructure.openai_embedding_gateway import (
    OpenAICompatibleEmbeddingGateway,
    probe_embedding,
)
from supportflow.model.infrastructure.openai_gateway import (
    OpenAICompatibleChatGateway,
    probe_chat_completion,
)
from supportflow.shared.errors import Forbidden, InvalidRequest, ModelConfigInvalid, NotFound

logger = logging.getLogger(__name__)

#: 连接测试的提示词刻意要求 JSON，以便同时验证 response_format 契约。
_PROBE_PROMPT = '只输出一个 JSON 对象：{"ok": true}'


class ModelConfigService:
    def __init__(
        self,
        repository: ModelConfigRepositoryPort,
        cipher_factory: Callable[[], SecretCipherPort],
        *,
        request_timeout_seconds: float = 30.0,
        max_attempts: int = 3,
    ) -> None:
        self._repository = repository
        # 惰性构造：主密钥未配置时，只有真正要做加解密才失败，
        # 而不是让整个容器（含 mock 模式）起不来。
        self._cipher_factory = cipher_factory
        self._timeout = request_timeout_seconds
        self._max_attempts = max_attempts

    # --- 管理用例（仅管理员） ------------------------------------------------

    def create(
        self,
        principal: Principal,
        *,
        capability: ModelCapability,
        protocol: ModelProtocol,
        base_url: str,
        model_name: str,
        api_key: str,
        embedding_dim: int | None = None,
    ) -> ModelConfig:
        self._require_admin(principal)
        validated_url = _validate_base_url(base_url)
        validated_model = _require_text(model_name, "model_name")
        _validate_capability_fields(capability, embedding_dim)

        # 加密失败（例如未配置主密钥）会在落库前抛出，绝不会留下半条明文记录。
        ciphertext = self._cipher_factory().encrypt(_require_text(api_key, "api_key"))
        return self._repository.add(
            NewModelConfig(
                capability=capability,
                protocol=protocol,
                base_url=validated_url,
                model_name=validated_model,
                embedding_dim=embedding_dim,
            ),
            ciphertext=ciphertext,
        )

    def list_configs(self, principal: Principal) -> list[ModelConfig]:
        self._require_admin(principal)
        return self._repository.list_all()

    def update(
        self,
        principal: Principal,
        config_id: UUID,
        *,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        embedding_dim: int | None = None,
    ) -> ModelConfig:
        self._require_admin(principal)
        existing = self._repository.find_by_id(config_id)
        if existing is None:
            raise NotFound("模型配置不存在")

        ciphertext: str | None = None
        if api_key is not None:
            ciphertext = self._cipher_factory().encrypt(_require_text(api_key, "api_key"))
        if embedding_dim is not None:
            _validate_capability_fields(existing.capability, embedding_dim)

        changes = ModelConfigUpdate(
            base_url=_validate_base_url(base_url) if base_url is not None else None,
            model_name=_require_text(model_name, "model_name") if model_name is not None else None,
            api_key=None,
            embedding_dim=embedding_dim,
        )
        return self._repository.update(existing.id, changes, ciphertext=ciphertext)

    def enable(self, principal: Principal, config_id: UUID) -> ModelConfig:
        self._require_admin(principal)
        existing = self._repository.find_by_id(config_id)
        if existing is None:
            raise NotFound("模型配置不存在")
        if not existing.api_key_configured:  # pragma: no cover - 密文非空由表结构保证
            raise ModelConfigInvalid("该配置没有可用的密钥密文")
        return self._repository.enable(existing.id)

    def test_connection(self, principal: Principal, config_id: UUID) -> ConnectionTestResult:
        """发起一次最小真实调用。

        **明确不返回 Mock 结果**：失败就是失败，并给出稳定错误码供前端展示
        （AGENTS.md §10：Mock 与真实结果必须分别报告）。
        """
        self._require_admin(principal)
        existing = self._repository.find_by_id(config_id)
        if existing is None:
            raise NotFound("模型配置不存在")
        if existing.capability is ModelCapability.EMBEDDING:
            ok, detail, latency_ms = self._probe_embedding(existing)
        else:
            ok, detail, latency_ms = self._probe_chat(existing)

        error_code = None if ok else detail.split(":", 1)[0]
        if not ok:
            logger.warning("模型连接测试失败: config_id=%s code=%s", existing.id, error_code)
        return ConnectionTestResult(
            ok=ok,
            latency_ms=latency_ms,
            model_name=existing.model_name,
            error_code=error_code,
            detail=detail[:400],
        )

    def _probe_chat(self, existing: ModelConfig) -> tuple[bool, str, int]:
        resolved = self.resolve_chat_config(existing.id)
        if resolved is None:  # pragma: no cover - 调用前已确认存在
            raise NotFound("模型配置不存在")
        with OpenAICompatibleChatGateway(
            base_url=resolved.base_url,
            api_key=resolved.api_key,
            model_name=resolved.model_name,
            timeout_seconds=resolved.timeout_seconds,
        ) as gateway:
            started = time.perf_counter()
            ok, detail = probe_chat_completion(gateway, prompt=_PROBE_PROMPT)
            return ok, detail, int((time.perf_counter() - started) * 1000)

    def _probe_embedding(self, existing: ModelConfig) -> tuple[bool, str, int]:
        """Embedding 连接测试：**同时校验实际维度与声明维度是否一致**。

        维度的差异必须被发现而不是被掩盖 —— 索引版本按「模型 + 维度」界定，
        声明 1024 而实际 768 会直接建出错误的向量列（AGENTS.md §7）。
        """
        resolved = self.resolve_embedding_config(existing.id)
        if resolved is None:  # pragma: no cover - 调用前已确认存在
            raise NotFound("模型配置不存在")
        if resolved.embedding_dim is None:  # pragma: no cover - 创建时已强制要求
            raise InvalidRequest("Embedding 配置缺少 embedding_dim")
        with OpenAICompatibleEmbeddingGateway(
            base_url=resolved.base_url,
            api_key=resolved.api_key,
            model_name=resolved.model_name,
            timeout_seconds=resolved.timeout_seconds,
        ) as gateway:
            started = time.perf_counter()
            ok, detail = probe_embedding(gateway, expected_dim=resolved.embedding_dim)
            return ok, detail, int((time.perf_counter() - started) * 1000)

    # --- 运行期用例（供组合根与 Worker 使用） --------------------------------

    def resolve_chat_config(self, config_id: UUID | None = None) -> ResolvedChatConfig | None:
        """解密并返回运行期所需的聊天配置。

        ``config_id`` 省略时取当前启用的聊天配置。返回 ``None`` 表示尚未配置。
        明文只存在于返回对象中，调用方不得记录它。
        """
        resolved = self._resolve(ModelCapability.CHAT, config_id)
        if resolved is None:
            return None
        config, api_key = resolved
        return ResolvedChatConfig(
            base_url=config.base_url,
            model_name=config.model_name,
            api_key=api_key,
            timeout_seconds=self._timeout,
            max_attempts=self._max_attempts,
        )

    def _resolve(
        self, capability: ModelCapability, config_id: UUID | None
    ) -> tuple[ModelConfig, str] | None:
        """取「配置 + 解密后的密钥」。两者都不是目标能力时返回 ``None``。

        明文只活在这个方法的返回值里，调用方不得记录它。
        """
        if config_id is None:
            enabled = self._repository.find_enabled(capability)
            if enabled is None:
                return None
            resolved_id = enabled.id
        else:
            resolved_id = config_id

        config = self._repository.find_by_id(resolved_id)
        ciphertext = self._repository.ciphertext_of(resolved_id)
        if config is None or not ciphertext or config.capability is not capability:
            return None
        return config, self._cipher_factory().decrypt(ciphertext)

    def resolve_embedding_config(
        self, config_id: UUID | None = None
    ) -> ResolvedEmbeddingConfig | None:
        """解密并返回运行期所需的 Embedding 配置。``None`` 表示尚未配置。"""
        resolved = self._resolve(ModelCapability.EMBEDDING, config_id)
        if resolved is None:
            return None
        config, api_key = resolved
        if config.embedding_dim is None:  # pragma: no cover - 创建时已强制要求
            return None
        return ResolvedEmbeddingConfig(
            base_url=config.base_url,
            model_name=config.model_name,
            api_key=api_key,
            timeout_seconds=self._timeout,
            embedding_dim=config.embedding_dim,
        )

    def embedding_capability_configured(self) -> bool:
        """Embedding 能力是否已启用配置。"""
        return self._repository.find_enabled(ModelCapability.EMBEDDING) is not None

    def chat_capability_configured(self) -> bool:
        """聊天能力是否已启用配置。用于判定按次指定的 ``real`` 是否可接受。"""
        return self._repository.find_enabled(ModelCapability.CHAT) is not None

    # --- 内部 ---------------------------------------------------------------

    @staticmethod
    def _require_admin(principal: Principal) -> None:
        if not principal.is_admin:
            raise Forbidden("仅管理员可以管理模型配置")


def _require_text(value: str, field: str) -> str:
    stripped = (value or "").strip()
    if not stripped:
        raise InvalidRequest(f"{field} 不能为空")
    return stripped


def _validate_base_url(value: str) -> str:
    candidate = _require_text(value, "base_url").rstrip("/")
    if not candidate.startswith(("http://", "https://")):
        raise InvalidRequest("base_url 必须以 http:// 或 https:// 开头")
    return candidate


def _validate_capability_fields(capability: ModelCapability, embedding_dim: int | None) -> None:
    """聊天不需要维度；Embedding 必须有维度，否则索引版本无法界定。"""
    if capability is ModelCapability.EMBEDDING:
        if embedding_dim is None:
            raise InvalidRequest("Embedding 配置必须提供 embedding_dim")
    elif embedding_dim is not None:
        raise InvalidRequest("聊天配置不应设置 embedding_dim")
