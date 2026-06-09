"""Gold layer: chunking and vector embeddings."""
import asyncio
import logging
from typing import TYPE_CHECKING, Any

from packages.auth_core.openai_client import embed_text_async
from packages.lakehouse.helpers import chunk_text, normalize_embedding

if TYPE_CHECKING:
    from packages.lakehouse.service import DataLakeService

logger = logging.getLogger(__name__)


class GoldLayer:
    def __init__(self, service: "DataLakeService"):
        self.service = service

    async def process_gold_layer(self, org_id: str | None = None) -> int:
        """Chunk Silver docs → Gold embeddings. Returns count processed."""
        query_ready = self.service.supabase.table("docs_silver").select("*").eq("status", "SILVER_READY").limit(5)
        query_error = self.service.supabase.table("docs_silver").select("*").eq("status", "ERROR").limit(5)
        if org_id and org_id != "ALL":
            query_ready = query_ready.eq("organization_id", org_id)
            query_error = query_error.eq("organization_id", org_id)

        res_ready = await asyncio.to_thread(query_ready.execute)
        res_error = await asyncio.to_thread(query_error.execute)
        docs = res_ready.data + res_error.data
        if not docs:
            return 0

        for doc in docs:
            await self._vectorize_document(doc)
        return len(docs)

    async def _vectorize_document(self, doc: dict[str, Any]) -> None:
        silver_id = doc["id"]
        text = doc.get("cleaned_text") or ""
        org_id = doc.get("organization_id")

        await asyncio.to_thread(
            self.service.supabase.table("docs_silver").update({"status": "CHUNKING"}).eq("id", silver_id).execute
        )

        try:
            chunks = chunk_text(text)
            if not chunks:
                await asyncio.to_thread(
                    self.service.supabase.table("docs_silver").update({"status": "COMPLETED"}).eq("id", silver_id).execute
                )
                return

            await asyncio.to_thread(
                self.service.supabase.table("docs_gold_vectors").delete().eq("silver_id", silver_id).execute
            )

            records = []
            for idx, chunk in enumerate(chunks):
                emb_values = await embed_text_async(chunk)
                records.append({
                    "silver_id": silver_id,
                    "chunk_index": idx,
                    "content": chunk,
                    "embedding": normalize_embedding(emb_values),
                    "organization_id": org_id,
                })

            if records:
                await asyncio.to_thread(
                    self.service.supabase.table("docs_gold_vectors").insert(records).execute
                )

            await asyncio.to_thread(
                self.service.supabase.table("docs_silver").update({"status": "COMPLETED"}).eq("id", silver_id).execute
            )
            logger.info("[GOLD] %s vetorizado em %d chunks.", silver_id, len(chunks))

        except Exception as e:
            await asyncio.to_thread(
                self.service.supabase.table("docs_silver").update({
                    "status": "ERROR",
                    "error_message": str(e)[:500],
                }).eq("id", silver_id).execute
            )
            logger.error("[GOLD] Erro no silver_id %s: %s", silver_id, e)
