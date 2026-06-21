import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from packages.auth_core.dependencies import validated_tenant_context
from packages.auth_core.limiter import limiter
from packages.auth_core.tenant import set_tenant_context
from packages.engine.input_guard import (
    BLOCKED_USER_RESPONSE,
    MessageVerdict,
    assess_user_message,
)
from packages.engine.service import dispatch_chat_test

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatTestRequest(BaseModel):
    message: str
    thread_id: str | None = None
    guided: bool = False  # dev chat opt-in: selection-based guided booking inline
    patient_id: str | None = None  # dev chat: simulated client (None = unregistered)

class ChatTestResponse(BaseModel):
    response: str
    agent: str
    tokens_used: int
    tokens_in: int = 0
    tokens_out: int = 0
    estimated_cost_brl: float = 0.0
    thread_id: str
    lead_name: str | None = None
    company_name: str | None = None
    email: str | None = None
    handoff: bool = False
    messages_count: int = 0
    scheduling_path: str | None = None
    triage_source: str | None = None
    step: dict | None = None

@router.post("/chat/test", response_model=ChatTestResponse)
@limiter.limit("30/minute")
async def test_chat(
    request: Request,
    payload: ChatTestRequest,
    org_id: str = Depends(validated_tenant_context),
):
    """Test endpoint to chat with the agent directly from the dashboard."""
    if org_id == "ALL":
        raise HTTPException(
            status_code=400,
            detail="Selecione uma organização específica para testar o chat.",
        )

    verdict = assess_user_message(payload.message)
    if verdict == MessageVerdict.BLOCKED:
        thread_id = payload.thread_id or "blocked"
        return ChatTestResponse(
            response=BLOCKED_USER_RESPONSE,
            agent="blocked",
            tokens_used=0,
            thread_id=thread_id,
            handoff=False,
            messages_count=0,
        )

    with set_tenant_context(org_id):
        result = await dispatch_chat_test(
            payload.message,
            payload.thread_id,
            org_id=org_id,
            guided_enabled=payload.guided,
            patient_id=payload.patient_id,
        )
    return ChatTestResponse(**result)
