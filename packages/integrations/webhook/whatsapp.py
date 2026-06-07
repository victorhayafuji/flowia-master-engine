import logging

import httpx

from packages.auth_core.database import db
from packages.auth_core.tenant import get_current_org_id

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
MOCK_TOKEN_PREFIXES = ("DEFAULT_", "your_", "test-")


class WhatsAppService:
    """
    Envio de mensagens via WhatsApp Cloud API (Meta Graph).
    Credenciais por tenant em organizations.whatsapp_phone_id / whatsapp_access_token.
    """

    def __init__(self):
        self.db = db
        self.base_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

    async def _get_org_whatsapp_credentials(self) -> dict[str, str]:
        org_id = get_current_org_id()
        if not org_id:
            raise ValueError("Tentativa de enviar WhatsApp sem Tenant Context")

        try:
            res = (
                self.db.client.table("organizations")
                .select("whatsapp_phone_id, whatsapp_access_token")
                .eq("id", org_id)
                .limit(1)
                .execute()
            )
            if res.data:
                row = res.data[0]
                phone_id = (row.get("whatsapp_phone_id") or "").strip()
                token = (row.get("whatsapp_access_token") or "").strip()
                if phone_id and token and not self._is_placeholder(token):
                    return {"phone_id": phone_id, "token": token}
        except Exception as exc:
            logger.error("Failed to load WhatsApp credentials for org %s: %s", org_id, exc)

        raise ValueError(
            f"WhatsApp não configurado para a organização {org_id}. "
            "Defina whatsapp_phone_id e whatsapp_access_token em organizations."
        )

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        lowered = value.lower()
        return any(lowered.startswith(p.lower()) for p in MOCK_TOKEN_PREFIXES)

    async def _post_message(self, phone_id: str, token: str, payload: dict) -> bool:
        url = f"{self.base_url}/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            logger.info("WhatsApp message sent via Graph API (phone_id=%s)", phone_id)
            return True
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response else ""
            logger.error(
                "WhatsApp API HTTP %s: %s",
                exc.response.status_code if exc.response else "?",
                body,
            )
            return False
        except Exception as exc:
            logger.error("Erro ao enviar WhatsApp: %s", exc)
            return False

    async def send_text_message(self, to_phone: str, message: str) -> bool:
        credentials = await self._get_org_whatsapp_credentials()
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message,
            },
        }
        return await self._post_message(
            credentials["phone_id"],
            credentials["token"],
            payload,
        )

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str = "pt_BR",
        components: list | None = None,
    ) -> bool:
        credentials = await self._get_org_whatsapp_credentials()
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        return await self._post_message(
            credentials["phone_id"],
            credentials["token"],
            payload,
        )
