"""冻结评测集的加载器。

``cases.json`` 与语料一起版本化；文件内容一经发布**不得修改**——
修指标口径或用例都要出新版本，否则前后两次评测不可比。
"""

from __future__ import annotations

import json
from pathlib import Path

from supportflow.evaluation.domain.models import (
    FrozenCase,
    FrozenCorpusDoc,
    FrozenSet,
)

DEFAULT_FROZEN_PATH = Path(__file__).resolve().parent / "cases.json"


def load_frozen_set(path: Path | None = None) -> FrozenSet:
    raw = json.loads((path or DEFAULT_FROZEN_PATH).read_text(encoding="utf-8"))
    corpus = [FrozenCorpusDoc(title=doc["title"], content=doc["content"]) for doc in raw["corpus"]]
    cases = [
        FrozenCase(
            case_key=case["case_key"],
            category=case["category"],
            subject=case["subject"],
            question=case["question"],
            expected_ticket_category=case.get("expected_ticket_category"),
            expected_source_ids=list(case.get("expected_source_ids", [])),
            expected_tools=list(case.get("expected_tools", [])),
            expect_handoff=bool(case.get("expect_handoff", False)),
        )
        for case in raw["cases"]
    ]
    return FrozenSet(version=int(raw.get("version", 1)), corpus=corpus, cases=cases)
