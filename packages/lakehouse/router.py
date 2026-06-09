import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from packages.auth_core.auth_service import get_user_by_username
from packages.auth_core.dependencies import admin_required, auth_required, validated_tenant_context
from packages.auth_core.openai_client import generate_text_async
from packages.auth_core.tenant import set_tenant_context
from packages.lakehouse.governance import (
    ACTIVE_DICTIONARY,
    execute_lakehouse_query_json,
    mask_pii_data,
)
from packages.lakehouse.service import DataLakeService, DuplicateDocumentError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Lakehouse"])


class IngestRequest(BaseModel):
    file_path: str


class SearchRequest(BaseModel):
    query: str
    match_threshold: float = 0.5
    match_count: int = 5


class QueryRequest(BaseModel):
    query: str


class GenerateSQLRequest(BaseModel):
    prompt: str


async def process_pipeline_background(org_id: str | None = None):
    try:
        service = DataLakeService()
        logger.info("[LAKEHOUSE] Silver layer (org=%s)", org_id)
        await service.process_silver_layer(org_id)
        logger.info("[LAKEHOUSE] Gold layer (org=%s)", org_id)
        await service.process_gold_layer(org_id)
        logger.info("[LAKEHOUSE] Pipeline finalizado.")
    except Exception as e:
        logger.error("[LAKEHOUSE] Erro no pipeline background: %s", e)


@router.post("/lakehouse/upload", dependencies=[Depends(auth_required)])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    org_id: str = Depends(validated_tenant_context),
):
    if org_id == "ALL":
        raise HTTPException(status_code=400, detail="Selecione uma organização específica para upload.")

    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Arquivo excede o limite de 10MB.")

        service = DataLakeService()
        with set_tenant_context(org_id):
            bronze_id = service.upload_document(
                file_bytes,
                file.filename or "documento",
                file.content_type or "application/octet-stream",
                org_id,
            )

        background_tasks.add_task(process_pipeline_background, org_id)
        return {
            "status": "success",
            "bronze_id": bronze_id,
            "message": "Upload concluído. Pipeline Bronze→Silver→Gold iniciado.",
        }
    except DuplicateDocumentError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Erro no upload do Lakehouse: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/lakehouse/ingest", dependencies=[Depends(auth_required)])
async def ingest_document(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    org_id: str = Depends(validated_tenant_context),
):
    if org_id == "ALL":
        raise HTTPException(status_code=400, detail="Selecione uma organização específica.")

    try:
        service = DataLakeService()
        with set_tenant_context(org_id):
            bronze_id = service.ingest_to_bronze(payload.file_path, org_id)

        background_tasks.add_task(process_pipeline_background, org_id)
        return {
            "status": "success",
            "bronze_id": bronze_id,
            "message": "Arquivo ingerido e processamento em background iniciado.",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Erro na ingestão do Lakehouse: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/lakehouse/search", dependencies=[Depends(auth_required)])
async def search_lakehouse(
    payload: SearchRequest,
    org_id: str = Depends(validated_tenant_context),
):
    try:
        service = DataLakeService()
        results = service.search_knowledge(
            payload.query,
            org_id=org_id,
            match_threshold=payload.match_threshold,
            match_count=payload.match_count,
        )
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error("Erro na busca do Lakehouse: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/lakehouse/sync", dependencies=[Depends(auth_required)])
async def sync_lakehouse(
    background_tasks: BackgroundTasks,
    org_id: str = Depends(validated_tenant_context),
):
    background_tasks.add_task(process_pipeline_background, org_id)
    return {"status": "success", "message": "Sincronização do Lakehouse iniciada em background."}


@router.get("/lakehouse/status", dependencies=[Depends(auth_required)])
async def lakehouse_status(org_id: str = Depends(validated_tenant_context)):
    service = DataLakeService()
    return {"status": "success", "data": service.get_pipeline_status(org_id)}


@router.get("/lakehouse/documents", dependencies=[Depends(auth_required)])
async def lakehouse_documents(
    org_id: str = Depends(validated_tenant_context),
    limit: int = 20,
):
    service = DataLakeService()
    return {"status": "success", "data": service.list_documents(org_id, limit)}


@router.get("/lakehouse/catalog", dependencies=[Depends(auth_required)])
async def get_catalog(request: Request):
    return {"status": "success", "catalog": ACTIVE_DICTIONARY}


@router.post("/lakehouse/query", dependencies=[Depends(admin_required)])
async def query_lakehouse(
    request: Request,
    payload: QueryRequest,
    current_user: str = Depends(auth_required),
):
    is_executive = False
    if current_user == "api_user":
        is_executive = True
    else:
        user_data = get_user_by_username(current_user)
        if user_data and user_data.get("role") in ["admin", "executive", "executivo"]:
            is_executive = True

    success, result_or_error = execute_lakehouse_query_json(payload.query)
    if not success:
        raise HTTPException(status_code=400, detail=result_or_error)

    if not is_executive and isinstance(result_or_error, list):
        result_or_error = mask_pii_data(result_or_error)

    return {"status": "success", "data": result_or_error, "rows": result_or_error}


@router.post("/lakehouse/generate-sql", dependencies=[Depends(admin_required)])
async def generate_sql(request: Request, payload: GenerateSQLRequest):
    try:
        schema_context = ""
        for table, info in ACTIVE_DICTIONARY.items():
            schema_context += f"Tabela: {table} (Camada {info['layer']}) - {info['description']}\nColunas:\n"
            for col, col_info in info["columns"].items():
                schema_context += f"  - {col} ({col_info['type']}): {col_info['description']}\n"

        prompt = (
            "Você é um tradutor especialista de linguagem natural para consultas SQL PostgreSQL.\n"
            "Seu objetivo é ler o pedido do usuário e traduzi-lo para uma consulta SELECT de leitura compatível com o seguinte dicionário de dados:\n\n"
            f"{schema_context}\n"
            "Regras Estritas:\n"
            "1. Retorne APENAS o código SQL puro. Não use blocos de Markdown ```sql, nem introdução, nem explicações.\n"
            "2. Use apenas comandos SELECT de leitura.\n"
            "3. Use apenas as tabelas e colunas descritas acima.\n"
            "4. Retorne apenas uma query.\n"
            "5. Não termine com ponto e vírgula (;).\n\n"
            f"Pedido do usuário: {payload.prompt}"
        )

        raw_sql = await generate_text_async(prompt)
        cleaned_sql = raw_sql.strip()

        if cleaned_sql.startswith("```"):
            lines = cleaned_sql.splitlines()
            if len(lines) > 1 and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if len(lines) > 0 and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned_sql = "\n".join(lines).strip()

        if cleaned_sql.endswith(";"):
            cleaned_sql = cleaned_sql[:-1].strip()

        logger.info("[LAKEHOUSE AI] Prompt: '%s' -> SQL Gerado: '%s'", payload.prompt, cleaned_sql)
        return {"status": "success", "query": cleaned_sql}

    except Exception as e:
        logger.error("Erro ao gerar SQL via IA: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro interno da IA: {str(e)}") from e
