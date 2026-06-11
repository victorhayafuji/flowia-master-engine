"""
Singleton SupabaseHandler — manages the single Supabase client connection.
NO business logic here. Only connection management.
"""
import logging

import httpx

from packages.auth_core.config import settings
from supabase import Client, ClientOptions, create_client

logger = logging.getLogger(__name__)

_CLIENT_TIMEOUT_SECONDS = 20


class SupabaseHandler:
    """
    Handler otimizado para interações com o Supabase.
    Centraliza a conexão e evita múltiplas inicializações.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = cls._initialize_client()
        return cls._instance

    @staticmethod
    def _initialize_client() -> Client:
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_ROLE

        if not url or not key:
            logger.error("❌ CRITICAL: SUPABASE_URL or SUPABASE_SERVICE_KEY missing!")
            return None

        try:
            http_client = httpx.Client(http2=False, timeout=_CLIENT_TIMEOUT_SECONDS)

            return create_client(
                url,
                key,
                options=ClientOptions(
                    httpx_client=http_client,
                    postgrest_client_timeout=_CLIENT_TIMEOUT_SECONDS,
                    storage_client_timeout=_CLIENT_TIMEOUT_SECONDS
                )
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {e}")
            return None

    @property
    def is_ready(self) -> bool:
        return self.client is not None

    def wait_for_ready(self, timeout: int = 3) -> bool:
        """Blocks until the client is ready or timeout is reached."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if self.client:
                return True
            self.client = self._initialize_client()
            if self.client:
                return True
            time.sleep(0.5)
        return False

    @classmethod
    def get_client(cls) -> Client:
        """Compatibility method for legacy scripts."""
        return cls().client


# Global singleton instance
db = SupabaseHandler()
