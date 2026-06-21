import logging

import httpx

from packages.auth_core.database import db
from packages.auth_core.tenant import get_current_org_id

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
MOCK_TOKEN_PREFIXES = ("DEFAULT_", "your_", "test-")
REQUEST_TIMEOUT_SECONDS = 30.0


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

    async def verify_credentials(self, phone_id: str, token: str) -> dict:
        """
        Read-only check of WhatsApp credentials against the Graph API.
        Returns {ok, verified_name, display_phone_number} on success,
        or {ok: False, error: <friendly message>} — never leaks token/stack.
        """
        phone_id = (phone_id or "").strip()
        token = (token or "").strip()
        if not phone_id or not token:
            return {"ok": False, "error": "Informe o phone_number_id e o token de acesso."}
        if self._is_placeholder(token):
            return {"ok": False, "error": "Token de acesso inválido (valor de exemplo)."}

        url = f"{self.base_url}/{phone_id}"
        params = {"fields": "verified_name,display_phone_number", "access_token": token}
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            return {
                "ok": True,
                "verified_name": data.get("verified_name"),
                "display_phone_number": data.get("display_phone_number"),
            }
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.warning("WhatsApp credential check failed: HTTP %s", status or "?")
            if status == 404:
                return {"ok": False, "error": "phone_number_id não encontrado na Meta. Confira o ID."}
            return {
                "ok": False,
                "error": "Credenciais inválidas ou sem permissão. Verifique o phone_number_id e o token.",
            }
        except Exception as exc:
            logger.warning("WhatsApp credential check error: %s", type(exc).__name__)
            return {
                "ok": False,
                "error": "Não foi possível validar as credenciais agora. Tente novamente em instantes.",
            }

    async def _post_message(self, phone_id: str, token: str, payload: dict) -> bool:
        url = f"{self.base_url}/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
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

    async def send_interactive_buttons(
        self, to_phone: str, body: str, buttons: list[dict]
    ) -> bool:
        """Reply buttons (máx. 3). ``buttons`` = [{id, title}] (title ≤ 20 chars)."""
        credentials = await self._get_org_whatsapp_credentials()
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:1024]},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": str(b["id"])[:256], "title": str(b["title"])[:20]},
                        }
                        for b in buttons[:3]
                    ]
                },
            },
        }
        return await self._post_message(credentials["phone_id"], credentials["token"], payload)

    async def send_interactive_list(
        self, to_phone: str, body: str, button_label: str, rows: list[dict]
    ) -> bool:
        """List message (máx. 10 linhas). ``rows`` = [{id, title, description?}]."""
        credentials = await self._get_org_whatsapp_credentials()
        if len(rows) > 10:
            logger.warning(
                "WhatsApp list truncated: %d options > 10 (pagination is v2.0)", len(rows)
            )
        section_rows = []
        for r in rows[:10]:
            row = {"id": str(r["id"])[:200], "title": str(r["title"])[:24]}
            if r.get("description"):
                row["description"] = str(r["description"])[:72]
            section_rows.append(row)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body[:1024]},
                "action": {
                    "button": (button_label or "Escolher")[:20],
                    "sections": [{"title": "Opções", "rows": section_rows}],
                },
            },
        }
        return await self._post_message(credentials["phone_id"], credentials["token"], payload)

    async def send_structured_step(self, to_phone: str, step: dict) -> bool:
        """Render a channel-agnostic StructuredStep (dict) as WhatsApp interactive.

        ``buttons`` for ≤3 options (Meta's reply-button limit), otherwise a ``list``
        (capped at 10 — extras are dropped with a warning; pagination is v2.0).
        Empty options fall back to a plain text message.
        """
        options = step.get("options") or []
        body = step.get("text") or ""
        if not options:
            return await self.send_text_message(to_phone, body)
        # Reply buttons cap at 3 (Meta limit). Use them only for ≤3 options — a
        # "buttons" step with >3 options falls back to a list, never dropping extras.
        if len(options) <= 3:
            return await self.send_interactive_buttons(to_phone, body, options)
        return await self.send_interactive_list(to_phone, body, "Ver opções", options)
