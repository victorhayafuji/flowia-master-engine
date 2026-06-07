import asyncio
import logging

from google import genai

from packages.auth_core.config import settings
from packages.lakehouse.bronze import BronzeLayer, DuplicateDocumentError
from packages.lakehouse.gold import GoldLayer
from packages.lakehouse.helpers import (
    ALLOWED_MIME_TYPES,
    BRONZE_BUCKET,
    EMBEDDING_DIM,
    chunk_text,
    clean_text,
    content_hash,
    dedupe_search_results,
    normalize_embedding,
    normalize_search_content,
)
from packages.lakehouse.search import SearchLayer
from packages.lakehouse.silver import SilverLayer
from supabase import Client, create_client

logger = logging.getLogger(__name__)

__all__ = [
    "ALLOWED_MIME_TYPES",
    "BRONZE_BUCKET",
    "DataLakeService",
    "DuplicateDocumentError",
    "EMBEDDING_DIM",
]


class DataLakeService:
    """
    Medallion pipeline: Bronze (raw storage) → Silver (OCR) → Gold (embeddings/RAG).
    Thin facade delegating to layer modules.
    """

    def __init__(self):
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE)
        self.ai_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.vision_model = settings.MODEL_NAME
        self.embedding_model = settings.EMBEDDING_MODEL_NAME
        self.ocr_semaphore = asyncio.Semaphore(5)
        self._ensure_bucket()
        self._init_layers()

    def _init_layers(self) -> None:
        self._bronze = BronzeLayer(self)
        self._silver = SilverLayer(self)
        self._gold = GoldLayer(self)
        self._search = SearchLayer(self)

    def _ensure_layers(self) -> None:
        if not hasattr(self, "_bronze"):
            self._init_layers()

    def _ensure_bucket(self) -> None:
        try:
            self.supabase.storage.create_bucket(BRONZE_BUCKET, options={"public": False})
            logger.info("Bucket '%s' criado.", BRONZE_BUCKET)
        except Exception:
            pass

    # Static helpers (backward compat for tests and callers)
    _normalize_embedding = staticmethod(normalize_embedding)
    _clean_text = staticmethod(clean_text)
    _chunk_text = staticmethod(chunk_text)
    _content_hash = staticmethod(content_hash)
    _normalize_search_content = staticmethod(normalize_search_content)
    _dedupe_search_results = staticmethod(dedupe_search_results)

    def upload_document(self, file_bytes: bytes, file_name: str, mime_type: str, org_id: str) -> str:
        self._ensure_layers()
        return self._bronze.upload_document(file_bytes, file_name, mime_type, org_id)

    def ingest_to_bronze(self, file_path: str, org_id: str | None = None) -> str:
        self._ensure_layers()
        return self._bronze.ingest_to_bronze(file_path, org_id)

    async def process_silver_layer(self, org_id: str | None = None) -> int:
        self._ensure_layers()
        return await self._silver.process_silver_layer(org_id)

    async def _ocr_single_document(self, doc):
        self._ensure_layers()
        return await self._silver._ocr_single_document(doc)

    async def process_gold_layer(self, org_id: str | None = None) -> int:
        self._ensure_layers()
        return await self._gold.process_gold_layer(org_id)

    async def _vectorize_document(self, doc):
        self._ensure_layers()
        return await self._gold._vectorize_document(doc)

    def search_knowledge(
        self,
        query: str,
        org_id: str | None = None,
        match_threshold: float = 0.5,
        match_count: int = 5,
    ):
        self._ensure_layers()
        return self._search.search_knowledge(query, org_id, match_threshold, match_count)

    def get_pipeline_status(self, org_id: str | None = None):
        self._ensure_layers()
        return self._search.get_pipeline_status(org_id)

    def list_documents(self, org_id: str | None = None, limit: int = 20):
        self._ensure_layers()
        return self._search.list_documents(org_id, limit)
