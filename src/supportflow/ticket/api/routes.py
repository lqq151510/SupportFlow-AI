"""工单接口。

* ``POST /tickets`` —— 写操作。必须携带 ``Idempotency-Key``，通过 CSRF 校验。
  成功返回 **202**（工单已落库、首次运行已入队），而不是 201 —— 因为资源尚未
  进入可交付状态，客户端应据 ``run_id`` 订阅事件流。
* ``GET /tickets`` / ``GET /tickets/{id}`` —— 读操作，无需 CSRF。可见性由
  ``TicketService`` 在服务端强制（``USER`` 仅见自己，他人工单返回 404）。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from supportflow.bootstrap.container import Services
from supportflow.identity.api.dependencies import (
    csrf_protected_principal,
    current_principal,
    get_services,
)
from supportflow.identity.domain.models import Principal
from supportflow.shared.errors import request_id_of
from supportflow.shared.http import idempotency_key, pagination
from supportflow.ticket.api.schemas import (
    TicketCreateRequest,
    TicketDetailOut,
    TicketOut,
    TicketPageOut,
)
from supportflow.ticket.domain.models import TicketStatus

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", status_code=202)
def submit_ticket(
    payload: TicketCreateRequest,
    request: Request,
    principal: Principal = Depends(csrf_protected_principal),
    services: Services = Depends(get_services),
    idempotency: str = Depends(idempotency_key),
) -> JSONResponse:
    submission = services.tickets.submit(
        principal,
        subject=payload.subject,
        body=payload.body,
        idempotency_key=idempotency,
        model_mode=payload.model_mode,
    )
    services.audit.record(
        action="ticket.submitted",
        actor_id=principal.user_id,
        resource_type="ticket",
        resource_id=str(submission.ticket_id),
        request_id=request_id_of(request),
        details={
            "ticket_no": submission.ticket_no,
            "run_id": str(submission.run_id),
            "replayed": submission.replayed,
        },
    )
    return JSONResponse(
        status_code=submission.status_code,
        content=submission.payload,
        headers={"Location": f"/api/v1/tickets/{submission.ticket_id}"},
    )


@router.get("", response_model=TicketPageOut)
def list_tickets(
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
    status: TicketStatus | None = Query(default=None),
    page: tuple[int, int] = Depends(pagination),
) -> TicketPageOut:
    limit, offset = page
    items, total = services.tickets.list_tickets(
        principal, status=status, limit=limit, offset=offset
    )
    return TicketPageOut(
        items=[TicketOut.of(ticket) for ticket in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{ticket_id}", response_model=TicketDetailOut)
def get_ticket(
    ticket_id: UUID,
    principal: Principal = Depends(current_principal),
    services: Services = Depends(get_services),
) -> TicketDetailOut:
    ticket = services.tickets.get_ticket(principal, ticket_id)
    return TicketDetailOut.of(ticket)
