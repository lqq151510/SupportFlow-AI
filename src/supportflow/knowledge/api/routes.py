"""知识库导入与内部检索 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile

from supportflow.bootstrap.container import Services
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.domain.models import Principal
from supportflow.knowledge.api.schemas import ImportJobOut, SearchOut, SearchPageOut
from supportflow.shared.http import idempotency_key

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
history_router = APIRouter(prefix="/history", tags=["history"])


@router.post("/imports", response_model=ImportJobOut, status_code=202)
def import_document(
    file: UploadFile = File(...),
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
    idempotency: str = Depends(idempotency_key),
) -> ImportJobOut:
    # 此版本同步完成 20MB 内的导入，仍按任务模型返回；后续 Worker 化不改变外部契约。
    result = services.knowledge.import_document(
        principal,
        filename=file.filename or "",
        content_type=file.content_type,
        raw=file.file.read(),
        idempotency_key=idempotency,
    )
    return ImportJobOut.of(result)


@history_router.post("/imports", response_model=ImportJobOut, status_code=202)
def import_history(
    file: UploadFile = File(...),
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
    idempotency: str = Depends(idempotency_key),
) -> ImportJobOut:
    result = services.knowledge.import_history(
        principal,
        filename=file.filename or "",
        raw=file.file.read(),
        idempotency_key=idempotency,
    )
    return ImportJobOut.of(result)


@router.get("/search", response_model=SearchPageOut)
def search(
    query: str = Query(min_length=1, max_length=1000),
    limit: int = Query(default=5, ge=1, le=20),
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> SearchPageOut:
    items = services.knowledge.search(principal, query, limit=limit)
    return SearchPageOut(query=query, items=[SearchOut.of(item) for item in items])
