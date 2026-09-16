"""从 FastAPI 应用导出冻结的 OpenAPI 快照到 docs/contracts/openapi.json。

前端类型由该快照经 openapi-typescript 生成（PLAN.md「接口与数据约定」），因此
快照必须可复现且纳入版本管理。导出不需要数据库，仅依赖应用导入时的路由注册。

用法（项目根目录）:
    uv run python script/dump_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 允许从任意 cwd 调用：把仓库根加入 sys.path 以便导入 supportflow 包。
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from supportflow.bootstrap.api import app  # noqa: E402


def main() -> int:
    schema = app.openapi()
    out = ROOT / "docs" / "contracts" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    paths = schema.get("paths", {})
    schemas = schema.get("components", {}).get("schemas", {})
    endpoints = sum(len(methods) for methods in paths.values())
    print(
        f"wrote {out.relative_to(ROOT)}: "
        f"{len(paths)} path groups, {endpoints} endpoints, {len(schemas)} schemas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
