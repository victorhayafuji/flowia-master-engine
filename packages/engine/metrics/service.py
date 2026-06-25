import logging
from datetime import datetime, timedelta
from typing import Any

from packages.auth_core.config import settings
from packages.auth_core.database import db
from packages.auth_core.finance import get_usd_to_brl

logger = logging.getLogger(__name__)

# Pricing Table (USD per 1M tokens) — OpenAI reference; see platform.openai.com/docs/pricing
PRICING = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o": {"in": 5.00, "out": 15.00},
    "text-embedding-3-small": {"in": 0.02, "out": 0.0},
    "default": {"in": 0.15, "out": 0.60},
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


def get_knowledge_gaps(
    organization_id: str | None = None, limit: int = 50, days: int = 30
) -> list[dict[str, Any]]:
    """Top perguntas sem resposta (lacunas) por nº de ocorrências, nos últimos N dias."""
    if not db.client:
        return []
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = (
            db.client.table("knowledge_gaps")
            .select("question, agent_type, occurrences, last_seen_at")
            .not_.is_("question", "null")
            .gte("last_seen_at", cutoff)
            .order("occurrences", desc=True)
            .limit(limit)
        )
        if organization_id:
            query = query.eq("organization_id", organization_id)
        return query.execute().data or []
    except Exception as e:
        logger.error("get_knowledge_gaps failed: %s", e)
        return []



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
    model_name: str = None,
    *,
    organization_id: str | None = None,
    scheduling_path: str | None = None,
    triage_source: str | None = None,
    channel: str | None = None,
    tools_called: list[str] | None = None,
):
    """Saves a conversation metric snapshot to Supabase."""
    model_name = model_name or settings.MODEL_NAME
    try:
        client = db.client
        data: dict[str, Any] = {
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
            "model_name": model_name,
            "tools_called": tools_called or [],
        }
        if organization_id:
            data["organization_id"] = organization_id
        if scheduling_path:
            data["scheduling_path"] = scheduling_path
        if triage_source:
            data["triage_source"] = triage_source
        if channel:
            data["channel"] = channel
        client.table("conversation_metrics").insert(data).execute()
        logger.info(
            "Metric saved | thread=%s tokens=%s path=%s triage=%s channel=%s",
            thread_id,
            tokens_total,
            scheduling_path,
            triage_source,
            channel,
        )
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


def get_recent_conversations(
    limit: int = 20,
    organization_id: str | None = None,
    days: int = 7,
) -> list:
    """Returns recent unique conversations with per-turn and per-thread token totals."""
    if not db.wait_for_ready(timeout=3):
        return []
    try:
        client = db.client
        query = (
            client.table("conversation_metrics")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit * 5)
        )
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        response = query.execute()

        rows = response.data or []
        thread_map = {}
        for r in rows:
            tid = r.get("thread_id")
            if tid and tid not in thread_map:
                thread_map[tid] = r
            if len(thread_map) >= limit:
                break

        threads = list(thread_map.values())
        if not threads:
            return []

        thread_ids = [t["thread_id"] for t in threads if t.get("thread_id")]
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        totals_query = (
            client.table("conversation_metrics")
            .select("thread_id, tokens_total")
            .gte("created_at", since)
            .in_("thread_id", thread_ids)
            .limit(5000)
        )
        if organization_id and organization_id != "ALL":
            totals_query = totals_query.eq("organization_id", organization_id)
        totals_rows = totals_query.execute().data or []

        thread_token_sums: dict[str, int] = {}
        for row in totals_rows:
            tid = row.get("thread_id")
            if not tid:
                continue
            thread_token_sums[tid] = thread_token_sums.get(tid, 0) + (row.get("tokens_total") or 0)

        for thread in threads:
            tid = thread.get("thread_id")
            turn_tokens = thread.get("tokens_total") or 0
            thread["tokens_turn"] = turn_tokens
            thread["tokens_thread_7d"] = thread_token_sums.get(tid, turn_tokens)

        return threads
    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}", exc_info=True)
        return []


def get_tokens_daily(days: int = 7, organization_id: str | None = None) -> list:
    """Returns daily token consumption for charts with optimized query."""
    if not db.wait_for_ready(timeout=3):
        return []
    try:
        client = db.client
        since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()

        query = (
            client.table("conversation_metrics")
            .select("created_at, tokens_total")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(1000)
        )
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        response = query.execute()

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


def get_scheduling_observability(
    organization_id: str | None = None,
    days: int = 7,
    channel: str | None = None,
) -> dict:
    """KPIs for hybrid scheduling: deterministic rate, channel split, token averages."""
    if not db.wait_for_ready(timeout=3):
        return {
            "days": days,
            "scheduling_turns": 0,
            "deterministic_count": 0,
            "llm_count": 0,
            "deterministic_rate_pct": 0.0,
            "by_channel": {},
            "avg_tokens_scheduling": 0,
        }

    try:
        client = db.client
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = (
            client.table("conversation_metrics")
            .select("scheduling_path, channel, tokens_total, agent_type")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(2000)
        )
        if organization_id and organization_id != "ALL":
            query = query.eq("organization_id", organization_id)
        if channel:
            query = query.eq("channel", channel)

        rows = query.execute().data or []

        scheduling_rows = [
            r for r in rows if r.get("scheduling_path") or r.get("agent_type") == "scheduling"
        ]
        deterministic = sum(1 for r in scheduling_rows if r.get("scheduling_path") == "deterministic")
        llm = sum(1 for r in scheduling_rows if r.get("scheduling_path") == "llm")
        total = len(scheduling_rows)

        by_channel: dict[str, int] = {}
        for row in rows:
            ch = row.get("channel") or "unknown"
            by_channel[ch] = by_channel.get(ch, 0) + 1

        token_sum = sum(r.get("tokens_total") or 0 for r in scheduling_rows)
        avg_tokens = round(token_sum / total, 1) if total else 0

        return {
            "days": days,
            "organization_id": organization_id,
            "channel_filter": channel,
            "scheduling_turns": total,
            "deterministic_count": deterministic,
            "llm_count": llm,
            "deterministic_rate_pct": round(deterministic / total * 100, 1) if total else 0.0,
            "by_channel": by_channel,
            "avg_tokens_scheduling": avg_tokens,
        }
    except Exception as e:
        logger.error(f"Failed to fetch scheduling observability: {e}", exc_info=True)
        raise e
