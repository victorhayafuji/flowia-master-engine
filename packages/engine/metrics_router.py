from fastapi import APIRouter, Depends

from packages.auth_core.dependencies import auth_required, validated_tenant_context
from packages.auth_core.system import get_system_health_metrics
from packages.engine.metrics.service import (
    get_dashboard_kpis,
    get_knowledge_gaps,
    get_recent_conversations,
    get_scheduling_observability,
    get_tokens_daily,
)

router = APIRouter(tags=["Metrics"])


@router.get("/metrics/kpis", dependencies=[Depends(auth_required)])
def get_kpis(org_id: str = Depends(validated_tenant_context)):
    return get_dashboard_kpis(organization_id=org_id if org_id != "ALL" else None)


@router.get("/metrics/conversations", dependencies=[Depends(auth_required)])
def get_conversations(
    limit: int = 20,
    days: int = 7,
    org_id: str = Depends(validated_tenant_context),
):
    org_filter = org_id if org_id != "ALL" else None
    return get_recent_conversations(limit, organization_id=org_filter, days=days)


@router.get("/metrics/tokens-daily", dependencies=[Depends(auth_required)])
def get_daily_tokens(days: int = 7, org_id: str = Depends(validated_tenant_context)):
    org_filter = org_id if org_id != "ALL" else None
    return get_tokens_daily(days, organization_id=org_filter)


@router.get("/metrics/scheduling-observability", dependencies=[Depends(auth_required)])
def scheduling_observability(
    org_id: str = Depends(validated_tenant_context),
    days: int = 7,
    channel: str | None = None,
):
    org_filter = org_id if org_id != "ALL" else None
    return get_scheduling_observability(
        organization_id=org_filter,
        days=days,
        channel=channel,
    )


@router.get("/metrics/knowledge-gaps", dependencies=[Depends(auth_required)])
def knowledge_gaps(
    org_id: str = Depends(validated_tenant_context),
    limit: int = 50,
    days: int = 30,
):
    org_filter = org_id if org_id != "ALL" else None
    return get_knowledge_gaps(organization_id=org_filter, limit=limit, days=days)


@router.get("/metrics/system-health", dependencies=[Depends(auth_required)])
def get_system_health():
    return get_system_health_metrics()


@router.get("/system/settings", dependencies=[Depends(auth_required)])
async def get_settings():
    from packages.auth_core.config import settings

    is_production = settings.LANGCHAIN_TRACING_V2.lower() == "true"
    return {
        "environment": "production" if is_production else "development",
        "session_ttl_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/system/settings", dependencies=[Depends(auth_required)])
async def update_settings(new_settings: dict):
    return {"status": "success", "message": "Configurações simuladas atualizadas."}
