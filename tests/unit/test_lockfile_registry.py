"""锁文件下载源一致性。

本机 ``uv lock`` 记录的下载源会在 pypi.org 与第三方镜像之间漂移（取决于当时代理/VPN
是否透明改写索引响应）—— 实测**两次相同输入**分别产出了两种源。一旦漂移，提交里会出现
上千行与改动无关的 URL 改写，而 ``uv lock --check`` 只会说「一致」，因为包与版本没变。

覆盖边界（如实说明，避免高估本断言的作用）：

- ``uv run`` 会先做 sync，并**自动把漂移的锁文件修回固定索引**，因此经由 ``uv run``
  跑测试时这里通常是「已自愈」状态 —— 漂移正是在「只跑 ``uv lock`` 就直接提交」的
  路径上溜过去的。
- 本断言覆盖的是**不经过 uv sync 的路径**：直接用解释器跑 pytest、``uv run --no-sync``、
  ``--frozen`` 安装，以及 CI 检出后直接验证锁文件。

因此把「锁文件只使用 ``pyproject.toml`` 里声明的默认索引」钉成断言：

- 漂移会在这些路径上直接失败，而不是等到提交时才被肉眼发现；
- 若确实要换源，必须同时改 ``pyproject.toml`` 的固定索引，让换源成为一次显式决定。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCKFILE = REPO_ROOT / "uv.lock"

_REGISTRY_RE = re.compile(r'^source = \{ registry = "([^"]+)" \}$', re.MULTILINE)


def _pinned_index() -> str:
    """取 ``pyproject.toml`` 声明的默认索引 URL。"""
    document = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    indexes = [
        index
        for index in document.get("tool", {}).get("uv", {}).get("index", [])
        if index.get("default")
    ]
    assert len(indexes) == 1, "pyproject.toml 必须声明恰好一个 default 索引"
    return str(indexes[0]["url"]).rstrip("/")


def test_lockfile_declares_only_the_pinned_registry() -> None:
    pinned = _pinned_index()
    registries = {value.rstrip("/") for value in _REGISTRY_RE.findall(LOCKFILE.read_text("utf-8"))}
    assert registries, "uv.lock 里没有解析到任何 registry 声明，锁文件结构可能已变化"
    assert registries == {pinned}, (
        "uv.lock 使用的下载源与 pyproject.toml 固定的索引不一致，说明加锁时被代理或"
        f"镜像改写了：锁文件={sorted(registries)}，固定索引={pinned}"
    )


def test_lockfile_pins_exactly_one_registry() -> None:
    """单一源：多源并存往往意味着漂移中途只改写了一部分条目。"""
    registries = {value.rstrip("/") for value in _REGISTRY_RE.findall(LOCKFILE.read_text("utf-8"))}
    assert len(registries) == 1
