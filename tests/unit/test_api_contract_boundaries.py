"""Cross-module assertions for public Pydantic response contracts."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "supportflow"
SERVER_DERIVED_IDENTITY_FIELDS = frozenset({"role", "user_id", "assignee_id", "submitter_id"})


def _response_models() -> Iterator[tuple[str, type[BaseModel]]]:
    for path in sorted(PACKAGE_ROOT.glob("*/api/schemas.py")):
        module_name = ".".join(path.with_suffix("").relative_to(PACKAGE_ROOT.parent).parts)
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value is not BaseModel
                and name.endswith("Out")
            ):
                yield f"{module_name}.{name}", value


def _input_models() -> Iterator[tuple[str, type[BaseModel]]]:
    for path in sorted(PACKAGE_ROOT.glob("*/api/schemas.py")):
        module_name = ".".join(path.with_suffix("").relative_to(PACKAGE_ROOT.parent).parts)
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value is not BaseModel
                and not name.endswith("Out")
            ):
                yield f"{module_name}.{name}", value


def _is_json_string(schema: dict[str, Any]) -> bool:
    if schema.get("type") == "string":
        return True
    alternatives = schema.get("anyOf")
    if not isinstance(alternatives, list):
        return False
    types = {
        item.get("type")
        for item in alternatives
        if isinstance(item, dict) and isinstance(item.get("type"), str)
    }
    return types == {"null", "string"}


def test_public_response_identifiers_are_json_strings() -> None:
    """防止数值数据库主键再次进入 REST 或 SSE 的 JSON 数据帧。"""
    violations: list[str] = []
    for model_name, model in _response_models():
        properties = model.model_json_schema(mode="serialization").get("properties", {})
        for field_name, schema in properties.items():
            if field_name != "id" and not field_name.endswith("_id"):
                continue
            if not isinstance(schema, dict) or not _is_json_string(schema):
                violations.append(f"{model_name}.{field_name}")

    assert not violations, "Public identifier fields must serialize as JSON strings: " + ", ".join(
        violations
    )


def test_business_requests_do_not_accept_server_derived_identity_fields() -> None:
    """角色和资源归属只能由服务端会话推导，不能由请求体指定。"""
    violations = [
        f"{model_name}.{field_name}"
        for model_name, model in _input_models()
        for field_name in model.model_fields
        if field_name in SERVER_DERIVED_IDENTITY_FIELDS
    ]

    assert not violations, "Business requests expose server-derived identity fields: " + ", ".join(
        violations
    )
