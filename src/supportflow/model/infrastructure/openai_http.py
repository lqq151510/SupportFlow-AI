"""OpenAI-compatible HTTP 客户端与上游错误分类。

聊天与 Embedding 两个网关共用这一层。**刻意只实现一处错误分类**：若两边各写一份，
迟早会出现「同一个上游响应在一个网关里可重试、在另一个里不可重试」的分歧，
而这类分歧只在故障时才显形。

分类规则（每条都有实测依据）：

| 上游情况 | 映射 | 可重试 |
|---|---|---|
| 超时、连接失败 | ``ModelUnavailable`` | 是 |
| 429 / 5xx，语义为限流或过载 | ``ModelUnavailable`` | 是 |
| 429，语义为**额度/余额不足** | ``ModelRequestRejected`` | **否** |
| 401 / 403 | ``ModelAuthenticationFailed`` | 否 |
| 其余 4xx | ``ModelRequestRejected`` | 否 |

实测依据：智谱在余额不足时返回 ``HTTP 429 + code=1113``，而模型过载时返回
``HTTP 429 + code=1305``。**同一个状态码承载两种完全不同的语义** —— 只看状态码会把
「账户没钱」误报成「服务暂时不可用」，重试三次后转人工，运维还看不出真正原因。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from supportflow.shared.errors import (
    AppError,
    ModelAuthenticationFailed,
    ModelRequestRejected,
    ModelUnavailable,
)

logger = logging.getLogger(__name__)

#: 可重试的状态码：临时性故障。
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

#: 明确的「额度/账单」类错误码。出现这些说明重试永远不会成功。
PERMANENT_QUOTA_CODES = frozenset(
    {
        "1113",  # 智谱：余额不足或无可用资源包
        "insufficient_quota",
        "billing_hard_limit_reached",
        "account_deactivated",
    }
)

#: 兜底关键词。上游错误码体系各不相同，按语义再判一次。
PERMANENT_QUOTA_HINTS = (
    "insufficient",
    "quota",
    "balance",
    "billing",
    "余额不足",
    "无可用资源包",
    "充值",
    "欠费",
)

#: 上游诊断信息保留的最大长度，避免把整页错误文档写进日志或数据库。
UPSTREAM_MESSAGE_LIMIT = 300


@dataclass(frozen=True, slots=True)
class UpstreamError:
    """上游错误信封的结构化视图。"""

    code: str | None
    message: str | None

    @property
    def is_permanent_quota_problem(self) -> bool:
        """额度/余额问题**不可重试** —— 重试再多次也是同样的结果。"""
        if (self.code or "").strip().lower() in PERMANENT_QUOTA_CODES:
            return True
        text = (self.message or "").lower()
        return any(hint in text for hint in PERMANENT_QUOTA_HINTS)


def parse_upstream_error(response: httpx.Response) -> UpstreamError:
    """抽取上游错误说明，供分类与管理员诊断。

    兼容三种实测过的信封：

    - 智谱：``{"error": {"code": "1113", "message": "余额不足…"}}``
    - OpenAI：``{"error": {"type": "insufficient_quota", "message": "…"}}``
    - 硅基流动：``{"code": 30014, "data": null, "message": "Token is invalid."}``
      —— **扁平结构，码与说明都在顶层**，没有 ``error`` 包裹。

    解析失败返回两个 ``None`` —— 诊断信息缺失不该影响错误分类。
    """
    empty = UpstreamError(code=None, message=None)
    try:
        body = response.json()
    except ValueError:
        return empty
    if not isinstance(body, dict):
        return empty

    error = body.get("error")
    code: object = None
    if isinstance(error, dict):
        message = error.get("message") or error.get("msg")
        # OpenAI 把语义放在 type 里，智谱放在 code 里。
        code = error.get("code") or error.get("type")
    elif isinstance(error, str):
        message = error
    else:
        # 扁平信封：码与说明都在顶层。
        message = body.get("message") or body.get("msg")
        code = body.get("code") or body.get("type")

    normalized_code = str(code) if isinstance(code, (int, str)) else None
    normalized_message = (
        message.strip()[:UPSTREAM_MESSAGE_LIMIT]
        if isinstance(message, str) and message.strip()
        else None
    )
    return UpstreamError(code=normalized_code, message=normalized_message)


def attach_upstream(error: AppError, upstream: UpstreamError) -> AppError:
    error.upstream_message = upstream.message
    return error


class OpenAICompatibleHttpClient:
    """共享的同步 HTTP 客户端与错误映射。

    刻意使用同步客户端：本仓库的业务事务与 Agent 执行都在线程池中同步运行
    （AGENTS.md §5 明确禁止在 ``async def`` 里做阻塞调用，也要求混合时在适配层切换）。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds)),
            # 本机 HTTP_PROXY 会劫持请求；模型调用必须直连或走用户显式配置的代理，
            # 因此这里不读环境代理，避免把凭据发给非预期主机。
            trust_env=False,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenAICompatibleHttpClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def post(self, path: str, payload: dict[str, object]) -> httpx.Response:
        """发起请求。**只把网络层失败映射为可重试错误**，状态码交给上层判定。"""
        try:
            return self._client.post(
                f"{self._base_url}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise ModelUnavailable(f"模型请求超时（{self._timeout:g}s）") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailable(f"模型服务连接失败：{type(exc).__name__}") from exc

    @staticmethod
    def check_status(response: httpx.Response) -> None:
        """按状态码与上游语义分类。错误体不原样外泄。

        上游原始说明只挂在 ``upstream_message`` 上供管理员诊断，不进入普通错误响应
        （见 ``AppError.upstream_message`` 的说明）。
        """
        if response.status_code < 400:
            return
        status = response.status_code
        upstream = parse_upstream_error(response)
        if status in (401, 403):
            raise attach_upstream(
                ModelAuthenticationFailed("模型服务拒绝了当前凭据，请检查 API Key 是否有效"),
                upstream,
            )
        if status in RETRYABLE_STATUS:
            if upstream.is_permanent_quota_problem:
                raise attach_upstream(
                    ModelRequestRejected(
                        f"上游账户额度或余额不足（HTTP {status}），重试无意义，请先处理计费"
                    ),
                    upstream,
                )
            raise attach_upstream(
                ModelUnavailable(f"模型服务暂时不可用（HTTP {status}）"), upstream
            )
        raise attach_upstream(
            ModelRequestRejected(f"模型服务拒绝了该请求（HTTP {status}）"), upstream
        )
