import logging

import requests

from packages.auth_core.config import settings

logger = logging.getLogger(__name__)

def send_slack_notification(message: str):
    """Envia notificação via Slack Webhook"""
    webhook_url = settings.SLACK_WEBHOOK_URL
    if not webhook_url:
        logger.warning("⚠️ SLACK_WEBHOOK_URL não configurado.")
        return
    try:
        requests.post(webhook_url, json={"text": message}, timeout=5)
    except Exception as e:
        logger.error(f"❌ Erro ao enviar Slack: {e}")
