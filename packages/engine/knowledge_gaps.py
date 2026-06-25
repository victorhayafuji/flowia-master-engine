"""Captura fail-soft de lacunas de conhecimento.

Registra as perguntas que o assistente não conseguiu responder pela base (RAG vazio
+ sem fallback de catálogo), para ops melhorar a base depois. É telemetria
*fire-and-forget*: qualquer erro é engolido — nunca pode quebrar o fluxo do agente.
"""
import logging

from packages.auth_core.config import settings
from packages.auth_core.database import db

logger = logging.getLogger(__name__)


def record_knowledge_gap(org_id: str | None, question: str, agent_type: str | None = None) -> None:
    """Upsert (incrementa ocorrências) de uma lacuna. Nunca levanta exceção."""
    if not settings.KNOWLEDGE_GAP_CAPTURE_ENABLED:
        return
    if not org_id or org_id == "ALL" or not question or not question.strip():
        return
    try:
        if not db.client:
            return
        db.client.rpc(
            "record_knowledge_gap",
            {"p_org": org_id, "p_question": question.strip()[:500], "p_agent": agent_type},
        ).execute()
    except Exception as e:  # noqa: BLE001 — fail-soft por design
        logger.debug("knowledge gap capture skipped: %s", e)
