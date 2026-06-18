
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Product line: salon (MVP) | clinic (future)
    PRODUCT_LINE: str = "salon"

    # OpenAI (chat, OCR, embeddings)
    OPENAI_API_KEY: str
    MODEL_NAME: str = "gpt-4o-mini"
    VISION_MODEL_NAME: str = "gpt-4o"
    EMBEDDING_MODEL_NAME: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 768

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE: str
    SUPABASE_DB_URL: str

    # WhatsApp / Meta
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_APP_SECRET: str = ""
    # Fail-closed: com APP_SECRET vazio (modelo multi-app "cliente traz a própria conta",
    # CLAUDE.md §20), inbound NÃO assinado só é aceito com este opt-in explícito.
    # Default seguro = rejeita webhook sem assinatura.
    WHATSAPP_ALLOW_UNSIGNED: bool = False

    # Public API base URL (used to show the WhatsApp webhook callback URL in the dashboard).
    # Default is the production Render API; override only for a custom domain.
    PUBLIC_API_URL: str = "https://flowia-api.onrender.com/api/v1"

    # LangGraph persistence: auto (postgres + memory fallback) | postgres | memory
    CHECKPOINTER_BACKEND: str = "auto"

    # Background jobs (reminders, no-show detection)
    SCHEDULER_ENABLED: bool = True

    # Scheduling: deterministic executor antes do LLM (desligar para testar/melhorar o agente)
    SCHEDULING_DETERMINISTIC_ENABLED: bool = True
    # smart = LLM só se executor não resolver; always = fallback LLM; never = só código
    SCHEDULING_LLM_FALLBACK: str = "smart"
    # Extractor LLM para turnos coloquiais/ambíguos antes do executor
    INTENT_EXTRACTOR_ENABLED: bool = True
    # Polish opcional pós-composer (validação factual fail-closed)
    RESPONSE_POLISH_ENABLED: bool = False
    WEBHOOK_DEDUP_RETENTION_DAYS: int = 7
    # Local webhook simulation (scripts/simulate_whatsapp_webhook.py) — dev only
    SIM_WHATSAPP_ORG_ID: str = ""
    SIM_WHATSAPP_PHONE_ID: str = "123456789"
    # WhatsApp inbound queue: inline (enqueue + process in API) | worker (dedicated worker consumes)
    WHATSAPP_QUEUE_MODE: str = "inline"

    # LangSmith Observability
    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_PROJECT: str = "flowia-master-engine"
    LANGCHAIN_API_KEY: str = ""

    # Security: CORS & Trusted Hosts
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

    # Security: Dashboard
    DASHBOARD_API_KEY: str
    DASHBOARD_JWT_SECRET: str

    # Integrations
    SLACK_WEBHOOK_URL: str = ""

    # Finance
    FALLBACK_USD_TO_BRL: float = 5.30

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    COOKIE_SECURE: bool = False  # True apenas em produção (HTTPS)

    # LGPD / Privacy
    PRIVACY_CONTACT_EMAIL: str = "privacidade@exemplo.com"
    PRIVACY_POLICY_URL: str = "https://www.gaussix.com/privacidade"
    CONVERSATION_METRICS_RETENTION_DAYS: int = 365
    CHECKPOINT_RETENTION_DAYS: int = 90

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Initialize global settings
settings = Settings()
