import logging
from datetime import datetime, timedelta

from packages.auth_core.config import settings
from packages.auth_core.database import db
from packages.auth_core.finance import get_usd_to_brl

logger = logging.getLogger(__name__)

# Pricing Table (USD per 1M tokens) - Reference: LangSmith/Provider Docs
PRICING = {
    "gemini-1.5-flash": {"in": 0.075, "out": 0.30},
    "gemini-1.5-pro": {"in": 3.50, "out": 10.50},
    "gemini-2.5-flash": {"in": 0.30, "out": 2.50},
    "gpt-4o": {"in": 5.00, "out": 15.00},
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "default": {"in": 0.10, "out": 0.40}
}


def calculate_cost(tokens_in: int, tokens_out: int, model_name: str = None, usd_to_brl: float = None) -> float:
    """Calculates cost in BRL based on model-specific pricing and live BACEN rate."""
    # Ensure inputs are numbers
    tokens_in = tokens_in or 0
    tokens_out = tokens_out or 0
    model_name = str(model_name or settings.MODEL_NAME).lower()

    # Find the closest model match or use default
    model_key = next((k for k in PRICING if k in model_name), "default")
    prices = PRICING[model_key]

    cost_usd = (tokens_in * (prices["in"] / 1_000_000)) + (tokens_out * (prices["out"] / 1_000_000))
    rate = usd_to_brl if usd_to_brl is not None else get_usd_to_brl()
    return cost_usd * rate



def save_conversation_metric(
    thread_id: str,
    sender_id: str,
    agent_type: str,
    messages_count: int,
    tokens_in: int,
    tokens_out: int,
    tokens_total: int,
    handoff_requested: bool = False,
    qualified: bool = False,
    ttq_seconds: float = None,
    sentiment_score: float = 0.0,
    is_frustrated: bool = False,
    model_name: str = None
):
    """Saves a conversation metric snapshot to Supabase."""
    model_name = model_name or settings.MODEL_NAME
    try:
        client = db.client
        data = {
            "thread_id": thread_id,
            "sender_id": sender_id,
            "agent_type": agent_type,
            "messages_count": messages_count,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tokens_total": tokens_total,
            "handoff_requested": handoff_requested,
            "qualified": qualified,
            "ttq_seconds": ttq_seconds,
            "sentiment_score": sentiment_score,
            "is_frustrated": is_frustrated,
            "model_name": model_name
        }
        client.table("conversation_metrics").insert(data).execute()
        logger.info(f"📊 Metric saved for thread={thread_id}, tokens={tokens_total}")
    except Exception as e:
        logger.error(f"Failed to save metric: {e}", exc_info=True)


def get_dashboard_kpis(organization_id: str | None = None) -> dict:
    """Aggregates KPIs from conversation_metrics for the dashboard."""
    # Espera até 3s pelo banco se ele não estiver pronto
    if not db.wait_for_ready(timeout=3):
        raise TimeoutError("Supabase connection timeout during KPI aggregation")

    try:
        client = db.client

        # Fetch more metrics to allow for better unique thread coverage
        query = client.table("conversation_metrics").select("*").order("created_at", desc=True).limit(2000)
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        response = query.execute()

        rows = response.data or []

        if not rows:
            return {
                "total_conversations": 0,
                "total_tokens": 0,
                "estimated_cost_brl": 0.0,
                "qualification_rate": 0.0,
                "avg_ttq_seconds": 0.0,
                "avg_messages": 0.0,
                "fallback_rate": 0.0,
                "sdr_count": 0,
                "support_count": 0,
            }

        # Deduplicate by thread_id: take only the most recent entry for each thread
        thread_map = {}
        for r in rows:
            tid = r.get("thread_id")
            if tid and tid not in thread_map:
                thread_map[tid] = r

        distinct_rows = list(thread_map.values())
        total = len(distinct_rows)

        total_tokens_in = sum(r.get("tokens_in") or 0 for r in distinct_rows)
        total_tokens_out = sum(r.get("tokens_out") or 0 for r in distinct_rows)
        total_tokens = total_tokens_in + total_tokens_out
        qualified_count = sum(1 for r in distinct_rows if r.get("qualified"))
        ttq_values = [r["ttq_seconds"] for r in distinct_rows if r.get("ttq_seconds") is not None]
        msg_values = [r.get("messages_count", 0) for r in distinct_rows]
        sdr_count = sum(1 for r in distinct_rows if r.get("agent_type") == "sdr")
        support_count = sum(1 for r in distinct_rows if r.get("agent_type") == "support")

        # Knowledge Gaps Count
        gap_count = client.table("knowledge_gaps").select("id", count="exact").execute().count or 0

        # Fetch exchange rate once to optimize looping
        usd_to_brl_rate = get_usd_to_brl()

        # Calculate precise cost based on unique threads
        total_cost_brl = sum(calculate_cost(
            r.get("tokens_in") or 0,
            r.get("tokens_out") or 0,
            r.get("model_name") or settings.MODEL_NAME,
            usd_to_brl=usd_to_brl_rate
        ) for r in distinct_rows)

        return {
            "total_conversations": total,
            "total_tokens": total_tokens,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "estimated_cost_brl": round(total_cost_brl, 4),
            "qualification_rate": round((qualified_count / total) * 100, 1) if total else 0.0,
            "avg_ttq_seconds": round(sum(ttq_values) / len(ttq_values), 1) if ttq_values else 0.0,
            "avg_messages": round(sum(msg_values) / len(msg_values), 1) if msg_values else 0.0,
            "avg_sentiment": round(sum(r.get("sentiment_score", 0) for r in distinct_rows) / total, 2) if total else 0.0,
            "frustration_rate": round((sum(1 for r in distinct_rows if r.get("is_frustrated")) / total) * 100, 1) if total else 0.0,
            "knowledge_gaps_count": gap_count,
            "qualified_count": qualified_count,
            "fallback_rate": 0.0,
            "sdr_count": sdr_count,
            "support_count": support_count,
            "usd_to_brl": round(usd_to_brl_rate, 4),
            "model_name": settings.MODEL_NAME,
        }
    except Exception as e:
        logger.error(f"Failed to fetch KPIs: {e}", exc_info=True)
        raise e


def get_recent_conversations(limit: int = 20) -> list:
    """Returns the most recent unique conversations for the dashboard table."""
    if not db.wait_for_ready(timeout=3):
        return []
    try:
        client = db.client
        # Fetch more to allow for deduplication
        response = client.table("conversation_metrics") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(limit * 5) \
            .execute()

        rows = response.data or []
        thread_map = {}
        for r in rows:
            tid = r.get("thread_id")
            if tid and tid not in thread_map:
                thread_map[tid] = r
            if len(thread_map) >= limit:
                break

        return list(thread_map.values())
    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}", exc_info=True)
        return []


def get_tokens_daily(days: int = 7) -> list:
    """Returns daily token consumption for charts with optimized query."""
    if not db.wait_for_ready(timeout=3):
        return []
    try:
        client = db.client
        since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()

        # Optimized: Fetch only needed columns and limit to avoid hanging
        response = client.table("conversation_metrics") \
            .select("created_at, tokens_total") \
            .gte("created_at", since) \
            .order("created_at", desc=True) \
            .limit(1000) \
            .execute()

        rows = response.data or []

        daily_stats = {}
        for r in rows:
            date_str = r["created_at"][:10]
            if date_str not in daily_stats:
                daily_stats[date_str] = {"date": date_str, "tokens": 0, "conversations": 0}
            daily_stats[date_str]["tokens"] += r.get("tokens_total", 0)
            daily_stats[date_str]["conversations"] += 1

        return sorted(list(daily_stats.values()), key=lambda x: x["date"])
    except Exception as e:
        logger.error(f"Failed to fetch daily tokens: {e}", exc_info=True)
        return []
