import json
import logging
import re
from pathlib import Path
from typing import Any

from packages.auth_core.database import db

logger = logging.getLogger(__name__)

_LEGACY_CRM_TABLES = frozenset({"leads_raw", "leads_silver", "leads"})
_DICTIONARY_PATH = Path(__file__).parent / "data" / "active_dictionary.json"


def _load_active_dictionary() -> dict[str, dict[str, Any]]:
    raw = json.loads(_DICTIONARY_PATH.read_text(encoding="utf-8"))
    return {name: meta for name, meta in raw.items() if name not in _LEGACY_CRM_TABLES}


# ==========================================
# 1. ACTIVE DICTIONARY (Unity Catalog Style)
# ==========================================
ACTIVE_DICTIONARY: dict[str, dict[str, Any]] = _load_active_dictionary()

# ==========================================
# 2. DATA GUARDRAILS (SQL Injection & Catalog Protection)
# ==========================================
def validate_sql_query(query: str) -> tuple[bool, str]:
    """
    Analisa e valida a consulta SQL enviada pelo LLM.
    Retorna (True, "") se válida e segura, ou (False, "motivo") caso viole os guardrails.
    """
    query_clean = query.strip().replace("\n", " ").replace("\r", " ")
    query_upper = query_clean.upper()

    # 1. Deve ser estritamente uma query de leitura (SELECT)
    if not query_upper.startswith("SELECT"):
        return False, "Operação negada: Apenas consultas SELECT de leitura são permitidas."

    # 2. Bloquear múltiplos statements e comentários (vetor clássico de bypass/injection)
    if ";" in query_clean:
        return False, "Operação negada: Consultas contendo ponto e vírgula (;) são bloqueadas."
    if "--" in query_clean or "/*" in query_clean or "*/" in query_clean:
        return False, "Operação negada: Comentários SQL (--, /*, */) são proibidos."

    # 3. Bloquear palavras-chave de escrita, modificação e DDL
    forbidden_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "REPLACE", "TRUNCATE", "GRANT", "DECLARE", "EXECUTE",
        "UPSERT", "MERGE", "INTO", "COPY"
    ]
    for kw in forbidden_keywords:
        # Busca por palavra inteira para evitar falso-positivo em nomes de coluna
        if re.search(rf"\b{kw}\b", query_upper):
            return False, f"Operação negada: O comando contém palavra-chave proibida: {kw}."

    # 4. Bloquear tabelas internas e tabelas do sistema/catálogo do PostgreSQL
    forbidden_patterns = [
        r"\bCHECKPOINTS\b", r"\bCHECKPOINT_BLOBS\b", r"\bCHECKPOINT_WRITES\b",
        r"\bCHECKPOINT_MIGRATIONS\b", r"\bDASHBOARD_USERS\b", r"\bSCHEMA_MIGRATIONS\b",
        r"\bINFORMATION_SCHEMA\b", r"\bPG_\w+\b"
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, query_upper):
            return False, "Operação negada: Acesso direto a tabelas do sistema ou internas é proibido."

    # 5. Garantir que referencia apenas as tabelas homologadas do dicionário
    whitelisted_tables = [t.upper() for t in ACTIVE_DICTIONARY.keys()]
    found_any = False
    for table in whitelisted_tables:
        if re.search(rf"\b{table}\b", query_upper):
            found_any = True
            break

    if not found_any:
        return False, "Operação negada: A consulta não referencia nenhuma tabela homologada do Lakehouse."

    return True, ""

# ==========================================
# 3. EXECUÇÃO DA QUERY
# ==========================================
def execute_lakehouse_query(query: str) -> str:
    """
    Valida a query através dos guardrails e, se aprovada, executa-a no Supabase.
    Retorna uma string contendo a tabela de resultados formatada em Markdown ou uma mensagem de erro.
    """
    logger.info(f"📊 [LAKEHOUSE] Recebida query para execução: {query}")

    # Validação do Guardrail
    is_safe, error_msg = validate_sql_query(query)
    if not is_safe:
        logger.warning(f"🚫 [LAKEHOUSE] Query bloqueada pelos guardrails: {error_msg}")
        return f"Erro de Segurança: {error_msg}"

    if not db.client:
        return "Erro: Conexão com o banco de dados indisponível."

    try:
        # Executa através da RPC criada no Supabase
        res = db.client.rpc("execute_read_only_query", {"query_text": query}).execute()
        data = res.data

        # Se a resposta indicar um erro retornado pelo PL/pgSQL
        if isinstance(data, dict) and "error" in data:
            return f"Erro no Banco de Dados: {data['error']}"

        if not data or not isinstance(data, list):
            return "Nenhum resultado encontrado para a consulta."

        # Formata os dados em tabela Markdown
        columns = list(data[0].keys())
        markdown_table = "| " + " | ".join(columns) + " |\n"
        markdown_table += "| " + " | ".join(["---"] * len(columns)) + " |\n"

        for row in data:
            row_vals = [str(row.get(col, "")) for col in columns]
            markdown_table += "| " + " | ".join(row_vals) + " |\n"

        return markdown_table

    except Exception as e:
        logger.error(f"❌ [LAKEHOUSE] Erro inesperado ao executar query: {e}")
        return f"Erro ao processar consulta: {str(e)}"


def execute_lakehouse_query_json(query: str) -> tuple[bool, Any]:
    """
    Valida a query através dos guardrails e, se aprovada, executa-a no Supabase.
    Retorna uma tupla (True, list_of_dicts) ou (False, error_message).
    """
    logger.info(f"📊 [LAKEHOUSE] Recebida query JSON para execução: {query}")

    # Validação do Guardrail
    is_safe, error_msg = validate_sql_query(query)
    if not is_safe:
        logger.warning(f"🚫 [LAKEHOUSE] Query bloqueada pelos guardrails: {error_msg}")
        return False, error_msg

    if not db.client:
        return False, "Conexão com o banco de dados indisponível."

    try:
        # Executa através da RPC criada no Supabase
        res = db.client.rpc("execute_read_only_query", {"query_text": query}).execute()
        data = res.data

        # Se a resposta indicar um erro retornado pelo PL/pgSQL
        if isinstance(data, dict) and "error" in data:
            return False, data['error']

        if data is None:
            return True, []

        return True, data

    except Exception as e:
        logger.error(f"❌ [LAKEHOUSE] Erro inesperado ao executar query: {e}")
        return False, "Erro ao executar a consulta."


# ==========================================
# 4. PII DATA MASKING
# ==========================================
def mask_email(email_str: str) -> str:
    """
    Mascaramento de e-mail: v***@domain.com
    Mantém o primeiro caractere da caixa postal e oculta o restante.
    """
    if not email_str or "@" not in email_str:
        return email_str
    try:
        parts = email_str.split("@", 1)
        local = parts[0]
        domain = parts[1]
        if len(local) <= 1:
            masked_local = local + "***"
        else:
            masked_local = local[0] + "***"
        return f"{masked_local}@{domain}"
    except Exception:
        return email_str


def mask_phone(phone_str: str) -> str:
    """
    Mascaramento de telefone: (11) 9****-**** ou (11) ****-****
    """
    if not phone_str:
        return phone_str

    digits = [c for c in phone_str if c.isdigit()]
    if not digits:
        return phone_str

    if len(digits) >= 10:
        ddd = "".join(digits[:2])
        if len(digits) == 11:
            nine = digits[2]
            return f"({ddd}) {nine}****-****"
        else:
            return f"({ddd}) ****-****"
    else:
        if len(phone_str) > 4:
            return phone_str[:2] + "****" + phone_str[-2:]
        return "****"


def mask_pii_data(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Varre os resultados de uma consulta e aplica mascaramento caso a chave/coluna
    sugira dados de e-mail ou telefone.
    """
    if not isinstance(rows, list):
        return rows

    masked_rows = []
    for row in rows:
        if not isinstance(row, dict):
            masked_rows.append(row)
            continue

        new_row = {}
        for key, val in row.items():
            if isinstance(val, str):
                k_lower = key.lower()
                if "email" in k_lower or "mail" in k_lower:
                    new_row[key] = mask_email(val)
                elif any(p in k_lower for p in ["telefone", "phone", "tel"]):
                    new_row[key] = mask_phone(val)
                elif "@" in val and "." in val and len(val) > 4:
                    new_row[key] = mask_email(val)
                else:
                    new_row[key] = val
            else:
                new_row[key] = val
        masked_rows.append(new_row)
    return masked_rows


