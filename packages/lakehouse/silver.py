"""Silver layer: OCR and text extraction from Bronze documents."""
import asyncio
import logging
from typing import TYPE_CHECKING, Any

from packages.auth_core.openai_client import extract_document_text_async
from packages.lakehouse.helpers import BRONZE_BUCKET, clean_text

if TYPE_CHECKING:
    from packages.lakehouse.service import DataLakeService

logger = logging.getLogger(__name__)


class SilverLayer:
    def __init__(self, service: "DataLakeService"):
        self.service = service

    async def process_silver_layer(self, org_id: str | None = None) -> int:
        """OCR pending Bronze docs → Silver. Returns count processed."""
        query = self.service.supabase.table("docs_bronze").select("*").eq("status", "PENDING").limit(5)
        if org_id and org_id != "ALL":
            query = query.eq("organization_id", org_id)

        res = await asyncio.to_thread(query.execute)
        if not res.data:
            return 0

        tasks = [self._ocr_single_document(doc) for doc in res.data]
        await asyncio.gather(*tasks)
        return len(res.data)

    async def _download_bronze_file(self, storage_path: str) -> bytes:
        return await asyncio.to_thread(
            self.service.supabase.storage.from_(BRONZE_BUCKET).download,
            storage_path,
        )

    async def _ocr_single_document(self, doc: dict[str, Any]) -> None:
        bronze_id = doc["id"]
        file_name = doc["file_name"]
        storage_path = doc["storage_path"]
        mime_type = doc.get("mime_type", "image/png")
        org_id = doc.get("organization_id")

        await asyncio.to_thread(
            self.service.supabase.table("docs_bronze").update({"status": "PROCESSING"}).eq("id", bronze_id).execute
        )

        try:
            file_bytes = await self._download_bronze_file(storage_path)
        except Exception as e:
            await self._mark_bronze_error(bronze_id, f"Download falhou: {e}")
            return

        async with self.service.ocr_semaphore:
            try:
                cleaned_text = await self._extract_text(file_bytes, mime_type, file_name)
                existing_silver = await asyncio.to_thread(
                    self.service.supabase.table("docs_silver")
                    .select("id")
                    .eq("bronze_id", bronze_id)
                    .limit(1)
                    .execute
                )
                silver_payload = {
                    "raw_text": cleaned_text,
                    "cleaned_text": cleaned_text,
                    "status": "SILVER_READY",
                    "organization_id": org_id,
                }
                if existing_silver.data:
                    await asyncio.to_thread(
                        self.service.supabase.table("docs_silver")
                        .update(silver_payload)
                        .eq("id", existing_silver.data[0]["id"])
                        .execute
                    )
                else:
                    await asyncio.to_thread(
                        self.service.supabase.table("docs_silver").insert({
                            "bronze_id": bronze_id,
                            **silver_payload,
                        }).execute
                    )
                await asyncio.to_thread(
                    self.service.supabase.table("docs_bronze").update({"status": "COMPLETED"}).eq("id", bronze_id).execute
                )
                logger.info("[SILVER] OCR concluído: %s", file_name)
            except Exception as e:
                await self._mark_bronze_error(bronze_id, str(e))
                logger.error("[SILVER] Erro em %s: %s", file_name, e)

    async def _extract_text(self, file_bytes: bytes, mime_type: str, file_name: str) -> str:
        if mime_type.startswith("text/"):
            return clean_text(file_bytes.decode("utf-8", errors="replace"))

        raw = await extract_document_text_async(file_bytes, mime_type, file_name)
        return clean_text(raw or f"[Sem texto extraído de {file_name}]")

    async def _mark_bronze_error(self, bronze_id: str, message: str) -> None:
        await asyncio.to_thread(
            self.service.supabase.table("docs_bronze").update({
                "status": "ERROR",
                "error_message": message[:500],
            }).eq("id", bronze_id).execute
        )
