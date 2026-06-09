"""Tests for Data Lake Phase 4 pipeline."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.lakehouse.service import EMBEDDING_DIM, DataLakeService, DuplicateDocumentError

ORG = "22222222-2222-2222-2222-222222222222"

PRICE_TABLE_OCR = (
    "FLOWIA - TABELA DE PRECOS 2026\n\n"
    "*   **Plano Starter:** R$ 299/mes\n"
    "*   **Plano Pro:** R$ 599/mes\n"
    "*   **Plano Enterprise:** sob consulta\n\n"
    "**Incluso:** agenda, pacientes, chatbot IA\n"
    "**SLA:** 99.5% uptime"
)


DENTAL_PRICE_OCR = (
    "CLINICA FLOWIA - TABELA DE PRECOS ODONTOLOGICOS\n\n"
    "*   **Limpeza (Profilaxia):** R$ 150 (30 min)\n"
    "*   **Consulta de Avaliacao:** R$ 100 (45 min)\n"
    "*   **Clareamento Dental:** R$ 800 (2 sessoes)\n"
)


class TestDataLakeServiceHelpers:
    def test_normalize_embedding_truncates(self):
        vec = [0.1] * 1000
        result = DataLakeService._normalize_embedding(vec, EMBEDDING_DIM)
        assert len(result) == EMBEDDING_DIM

    def test_normalize_embedding_pads(self):
        vec = [0.5] * 100
        result = DataLakeService._normalize_embedding(vec, EMBEDDING_DIM)
        assert len(result) == EMBEDDING_DIM
        assert result[100] == 0.0

    def test_clean_text_removes_null_bytes(self):
        assert "\x00" not in DataLakeService._clean_text("hello\x00world")

    def test_chunk_text_splits_price_table(self):
        chunks = DataLakeService._chunk_text(PRICE_TABLE_OCR)
        assert len(chunks) >= 2
        assert any("R$ 299" in c for c in chunks)
        assert any("Enterprise" in c for c in chunks)

    def test_chunk_text_splits_dental_price_table(self):
        chunks = DataLakeService._chunk_text(DENTAL_PRICE_OCR)
        assert len(chunks) >= 1
        assert any("R$ 150" in c for c in chunks)
        assert any("Limpeza" in c for c in chunks)

    def test_chunk_text_normalizes_crlf(self):
        text = "# FAQ FlowIA\r\n\r\n## Agendamento\r\nTexto de agendamento longo aqui.\r\n\r\n## WhatsApp\r\nDisponivel no plano Enterprise."
        chunks = DataLakeService._chunk_text(text)
        assert len(chunks) >= 2
        assert any("Agendamento" in c for c in chunks)
        assert any("WhatsApp" in c or "Enterprise" in c for c in chunks)

    def test_dedupe_search_results_removes_identical_chunks(self):
        price_chunk = "* **Plano Starter:** R$ 299/mes\n* **Plano Pro:** R$ 599/mes"
        results = [
            {"content": price_chunk, "similarity": 0.74},
            {"content": price_chunk, "similarity": 0.73},
            {"content": "## Suporte\nHorario comercial", "similarity": 0.61},
        ]
        deduped = DataLakeService._dedupe_search_results(results, limit=5)
        assert len(deduped) == 2
        assert deduped[0]["similarity"] == 0.74

    def test_dedupe_search_results_keeps_distinct_chunks(self):
        results = [
            {"content": "Plano Enterprise sob consulta", "similarity": 0.8},
            {"content": "Plano Pro R$ 599", "similarity": 0.7},
            {"content": "# Tabela de precos", "similarity": 0.5},
        ]
        deduped = DataLakeService._dedupe_search_results(results, limit=3)
        assert len(deduped) == 3

    def test_content_hash_is_deterministic(self):
        h1 = DataLakeService._content_hash(b"same-bytes")
        h2 = DataLakeService._content_hash(b"same-bytes")
        assert h1 == h2
        assert h1 != DataLakeService._content_hash(b"other")


class TestDataLakeVectorize:
    @pytest.mark.asyncio
    async def test_vectorize_inserts_one_record_per_chunk(self, mocker):
        mocker.patch.object(DataLakeService, "__init__", lambda self: None)
        service = DataLakeService()
        service.embedding_model = "text-embedding-3-small"
        service.supabase = MagicMock()

        mock_embed = mocker.patch(
            "packages.lakehouse.gold.embed_text_async",
            new=AsyncMock(return_value=[0.1] * EMBEDDING_DIM),
        )

        doc = {
            "id": "silver-uuid-1",
            "cleaned_text": PRICE_TABLE_OCR,
            "organization_id": ORG,
        }

        await service._vectorize_document(doc)

        chunks = DataLakeService._chunk_text(PRICE_TABLE_OCR)
        assert mock_embed.await_count == len(chunks)

        insert_call = service.supabase.table.return_value.insert.call_args
        records = insert_call[0][0]
        assert len(records) == len(chunks)
        assert service.supabase.table.return_value.delete.return_value.eq.return_value.execute.called


class TestDataLakeUpload:
    def test_upload_rejects_all_org(self):
        service = DataLakeService.__new__(DataLakeService)
        with pytest.raises(ValueError, match="organização"):
            service.upload_document(b"data", "test.png", "image/png", "ALL")

    def test_upload_rejects_unsupported_mime(self, mocker):
        mocker.patch.object(DataLakeService, "__init__", lambda self: None)
        service = DataLakeService()
        service.supabase = MagicMock()

        with pytest.raises(ValueError, match="não suportado"):
            service.upload_document(b"data", "file.exe", "application/x-msdownload", ORG)

    def test_upload_rejects_duplicate_hash(self, mocker):
        mocker.patch.object(DataLakeService, "__init__", lambda self: None)
        service = DataLakeService()
        service.supabase = MagicMock()

        mock_existing = MagicMock()
        mock_existing.data = [{"id": "existing-id", "file_name": "precos.png"}]
        service.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = mock_existing

        with pytest.raises(DuplicateDocumentError, match="identico"):
            service.upload_document(b"duplicate", "precos.png", "image/png", ORG)

    def test_upload_persists_content_hash(self, mocker):
        mocker.patch.object(DataLakeService, "__init__", lambda self: None)
        service = DataLakeService()
        service.supabase = MagicMock()

        mock_empty = MagicMock()
        mock_empty.data = []
        service.supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = mock_empty

        mock_insert = MagicMock()
        mock_insert.data = [{"id": "new-bronze-id"}]
        service.supabase.table.return_value.insert.return_value.execute.return_value = mock_insert

        file_bytes = b"unique-content"
        service.upload_document(file_bytes, "doc.txt", "text/plain", ORG)

        insert_payload = service.supabase.table.return_value.insert.call_args[0][0]
        assert insert_payload["content_hash"] == DataLakeService._content_hash(file_bytes)


class TestDataLakeStatus:
    def test_get_pipeline_status_structure(self, mocker):
        mocker.patch.object(DataLakeService, "__init__", lambda self: None)
        service = DataLakeService()
        service.supabase = MagicMock()

        mock_execute = MagicMock()
        mock_execute.count = 3
        service.supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_execute
        service.supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_execute

        status = service.get_pipeline_status(ORG)
        assert "bronze_pending" in status
        assert "gold_vectors" in status


class TestDataLakeRoutes:
    def test_lakehouse_status_requires_auth(self, client):
        response = client.get("/api/v1/lakehouse/status", headers={"x-organization-id": ORG})
        assert response.status_code == 401

    def test_lakehouse_status_with_auth(self, client, user_token, mocker):
        mocker.patch(
            "packages.lakehouse.router.DataLakeService",
            return_value=mocker.MagicMock(
                get_pipeline_status=mocker.MagicMock(return_value={"bronze_pending": 1})
            ),
        )
        response = client.get(
            "/api/v1/lakehouse/status",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG},
        )
        assert response.status_code == 200
        assert response.json()["data"]["bronze_pending"] == 1

    def test_upload_rejects_all_org(self, client, admin_token):
        response = client.post(
            "/api/v1/lakehouse/upload",
            cookies={"session_token": admin_token},
            headers={"x-organization-id": "ALL"},
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400

    def test_upload_returns_409_on_duplicate(self, client, admin_token, mocker):
        mocker.patch(
            "packages.lakehouse.router.DataLakeService",
            return_value=mocker.MagicMock(
                upload_document=mocker.MagicMock(
                    side_effect=DuplicateDocumentError("Documento identico ja ingerido: precos.png")
                )
            ),
        )
        response = client.post(
            "/api/v1/lakehouse/upload",
            cookies={"session_token": admin_token},
            headers={"x-organization-id": ORG},
            files={"file": ("precos.png", b"dup", "image/png")},
        )
        assert response.status_code == 409
