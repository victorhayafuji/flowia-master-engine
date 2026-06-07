"""Bronze layer: raw document upload and ingestion."""
import logging
import mimetypes
import os
import re
import uuid
from typing import TYPE_CHECKING

from packages.lakehouse.helpers import ALLOWED_MIME_TYPES, BRONZE_BUCKET, content_hash

if TYPE_CHECKING:
    from packages.lakehouse.service import DataLakeService

logger = logging.getLogger(__name__)


class DuplicateDocumentError(ValueError):
    """Raised when an identical file was already ingested for the organization."""


class BronzeLayer:
    def __init__(self, service: "DataLakeService"):
        self.service = service

    @staticmethod
    def _storage_path(org_id: str, file_name: str) -> str:
        safe_name = re.sub(r"[^\w.\-]", "_", file_name)
        return f"{org_id}/{uuid.uuid4()}_{safe_name}"

    def upload_document(
        self,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        org_id: str,
    ) -> str:
        """Uploads raw file to Bronze bucket and registers in docs_bronze."""
        if org_id == "ALL":
            raise ValueError("Selecione uma organização específica para upload.")

        resolved_mime = mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        if resolved_mime not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Tipo de arquivo não suportado: {resolved_mime}")

        digest = content_hash(file_bytes)
        existing = (
            self.service.supabase.table("docs_bronze")
            .select("id, file_name")
            .eq("organization_id", org_id)
            .eq("content_hash", digest)
            .in_("status", ["PENDING", "PROCESSING", "COMPLETED"])
            .limit(1)
            .execute()
        )
        if existing.data:
            existing_name = existing.data[0].get("file_name", file_name)
            raise DuplicateDocumentError(f"Documento identico ja ingerido: {existing_name}")

        storage_path = self._storage_path(org_id, file_name)
        self.service.supabase.storage.from_(BRONZE_BUCKET).upload(
            storage_path,
            file_bytes,
            file_options={"content-type": resolved_mime, "upsert": "false"},
        )

        res = self.service.supabase.table("docs_bronze").insert({
            "file_name": file_name,
            "storage_path": storage_path,
            "mime_type": resolved_mime,
            "file_size": len(file_bytes),
            "content_hash": digest,
            "status": "PENDING",
            "organization_id": org_id,
        }).execute()

        return res.data[0]["id"]

    def ingest_to_bronze(self, file_path: str, org_id: str | None = None) -> str:
        """Legacy: ingest local file (dev/mocks). Uploads to Storage when org_id provided."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        resolved_org = org_id or "00000000-0000-0000-0000-000000000001"
        return self.upload_document(file_bytes, file_name, mime_type, resolved_org)
