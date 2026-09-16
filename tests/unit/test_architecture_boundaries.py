"""Architecture boundary checks for the Python application modules."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "supportflow"
FORBIDDEN_DOMAIN_IMPORTS = frozenset(
    {
        "anthropic",
        "fastapi",
        "httpx",
        "langchain",
        "langchain_core",
        "langgraph",
        "openai",
        "pgvector",
        "psycopg",
        "sqlalchemy",
    }
)
MODEL_SDK_IMPORTS = frozenset({"anthropic", "httpx", "openai"})
MODEL_SDK_ADAPTER_ROOT = PACKAGE_ROOT / "model" / "infrastructure"
MULTI_TENANT_MARKER = re.compile(r"tenant(?:[_-]?(?:id|code|name))", flags=re.IGNORECASE)
LEGACY_RUNTIME_MARKER = re.compile(
    r"backend/|mvn|maven|spring-boot|src-tauri|tauri|jpackage|build:dmg|java-kotlin",
    flags=re.IGNORECASE,
)
ACTIVE_DELIVERY_FILES = (
    REPO_ROOT / "Dockerfile",
    REPO_ROOT / "docker-compose.yml",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / ".github" / "workflows" / "verify.yml",
    REPO_ROOT / "frontend" / "package.json",
)


def _domain_modules() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*/domain/*.py"))


def _import_roots(path: Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module.partition(".")[0]


def test_domain_layers_do_not_import_framework_database_or_model_sdks() -> None:
    """Keep domain rules portable and independent from delivery infrastructure."""
    violations = [
        f"{path.relative_to(PACKAGE_ROOT)} imports {import_root}"
        for path in _domain_modules()
        for import_root in _import_roots(path)
        if import_root in FORBIDDEN_DOMAIN_IMPORTS
    ]

    assert not violations, "Domain-layer dependency violations:\n" + "\n".join(violations)


def test_model_sdk_imports_are_confined_to_model_adapters() -> None:
    """业务模块必须经 ModelGateway 调用模型，不得自行持有 HTTP/SDK 客户端。"""
    violations = [
        f"{path.relative_to(PACKAGE_ROOT)} imports {import_root}"
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        for import_root in _import_roots(path)
        if import_root in MODEL_SDK_IMPORTS and MODEL_SDK_ADAPTER_ROOT not in path.parents
    ]

    assert not violations, "Model SDK imports outside model adapters:\n" + "\n".join(violations)


def test_python_runtime_and_migrations_do_not_reintroduce_multi_tenancy() -> None:
    """新版是单工作区；数据模型与迁移不得为 tenant 隔离预留字段。"""
    paths = [
        *PACKAGE_ROOT.rglob("*.py"),
        *(REPO_ROOT / "migrations").rglob("*.py"),
    ]
    violations = [
        str(path.relative_to(REPO_ROOT))
        for path in sorted(paths)
        if MULTI_TENANT_MARKER.search(path.read_text(encoding="utf-8"))
    ]

    assert not violations, "Single-workspace architecture forbids tenant fields:\n" + "\n".join(
        violations
    )


def test_active_delivery_configuration_does_not_reintroduce_legacy_java_runtime() -> None:
    """Compose、CI 和前端构建入口只能交付 Python Web 架构。"""
    missing = [
        str(path.relative_to(REPO_ROOT)) for path in ACTIVE_DELIVERY_FILES if not path.exists()
    ]
    assert not missing, "Expected active delivery files are missing: " + ", ".join(missing)

    violations = [
        str(path.relative_to(REPO_ROOT))
        for path in ACTIVE_DELIVERY_FILES
        if LEGACY_RUNTIME_MARKER.search(path.read_text(encoding="utf-8"))
    ]
    assert not violations, "Active delivery configuration references legacy runtime: " + ", ".join(
        violations
    )
