"""Semantic search and pipeline status queries."""
import logging
from typing import TYPE_CHECKING, Any

from packages.lakehouse.helpers import dedupe_search_results, normalize_embedding

if TYPE_CHECKING:
    from packages.lakehouse.service import DataLakeService

logger = logging.getLogger(__name__)


class SearchLayer:
    def __init__(self, service: "DataLakeService"):
        self.service = service

    def search_knowledge(
        self,
        query: str,
        org_id: str | None = None,
        match_threshold: float = 0.5,
        match_count: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search in Gold layer, optionally filtered by organization."""
        try:
            emb_res = self.service.ai_client.models.embed_content(
                model=self.service.embedding_model,
                contents=query,
            )
            query_embedding = normalize_embedding(emb_res.embeddings[0].values)

            rpc_params: dict[str, Any] = {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count * 2,
            }
            if org_id and org_id != "ALL":
                rpc_params["filter_org_id"] = org_id

            response = self.service.supabase.rpc("match_documents", rpc_params).execute()
            return dedupe_search_results(response.data or [], match_count)

        except Exception as e:
            logger.error("[SEARCH] Erro na busca vetorial: %s", e)
            return []

    def get_pipeline_status(self, org_id: str | None = None) -> dict[str, Any]:
        """Returns document counts per layer and status."""
        def _count(table: str, status: str | None = None) -> int:
            q = self.service.supabase.table(table).select("id", count="exact")
            if org_id and org_id != "ALL":
                q = q.eq("organization_id", org_id)
            if status:
                q = q.eq("status", status)
            return q.limit(1).execute().count or 0

        return {
            "bronze_pending": _count("docs_bronze", "PENDING"),
            "bronze_processing": _count("docs_bronze", "PROCESSING"),
            "bronze_completed": _count("docs_bronze", "COMPLETED"),
            "bronze_error": _count("docs_bronze", "ERROR"),
            "silver_ready": _count("docs_silver", "SILVER_READY"),
            "silver_completed": _count("docs_silver", "COMPLETED"),
            "gold_vectors": _count("docs_gold_vectors"),
        }

    def list_documents(self, org_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Lists recent Bronze documents with metadata."""
        q = (
            self.service.supabase.table("docs_bronze")
            .select("id, file_name, status, mime_type, file_size, created_at, error_message")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if org_id and org_id != "ALL":
            q = q.eq("organization_id", org_id)
        return q.execute().data or []
