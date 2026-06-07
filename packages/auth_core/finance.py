"""
Currency Service — Real-time USD/BRL exchange rate from BACEN (Banco Central do Brasil).

Uses the public PTAX API (OData/Olinda) with in-memory TTL cache to avoid
hitting the endpoint on every single cost calculation.

Fallback chain:
  1. BACEN PTAX API (live)
  2. In-memory cached value (survives API downtime for up to 6 hours)
  3. settings.USD_TO_BRL from .env (ultimate fallback)
"""

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from packages.auth_core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache — stores the last successful rate + timestamp
# ---------------------------------------------------------------------------
_cache: dict = {
    "rate": None,
    "fetched_at": 0.0,
}

# How long (seconds) we trust the cached value before re-fetching.
_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours (PTAX usually updates once a day)
_REQUEST_TIMEOUT = 5  # seconds


def _fetch_ptax_rate() -> float | None:
    """Fetches the latest PTAX sell rate from the BACEN Olinda API."""
    today = datetime.now(ZoneInfo("America/Sao_Paulo"))

    # Try today first, then yesterday (weekends / holidays have no quotes)
    for days_back in range(0, 5):
        target = today - timedelta(days=days_back)
        date_str = target.strftime("%m-%d-%Y")
        url = (
            "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            f"CotacaoDolarDia(dataCotacao=@dataCotacao)"
            f"?@dataCotacao='{date_str}'"
            f"&$format=json"
            f"&$orderby=dataHoraCotacao desc"
            f"&$top=1"
        )
        try:
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            values = data.get("value", [])
            if values:
                rate = values[0].get("cotacaoVenda")
                if rate:
                    logger.info(f"💱 BACEN PTAX fetched: R$ {rate:.4f} (date={date_str})")
                    return float(rate)
        except Exception as e:
            logger.warning(f"BACEN API attempt for {date_str} failed: {e}")
            continue

    return None


def get_usd_to_brl() -> float:
    """
    Returns the current USD → BRL exchange rate.

    Resolution order:
      1. Cached value (if still valid within TTL)
      2. Live fetch from BACEN PTAX
      3. settings.FALLBACK_USD_TO_BRL fallback
    """
    now = time.time()

    # 1. Return cached if still fresh
    if _cache["rate"] is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["rate"]

    # 2. Try live fetch
    rate = _fetch_ptax_rate()
    if rate is not None:
        _cache["rate"] = rate
        _cache["fetched_at"] = now
        return rate

    # 3. If cache exists but is stale, still better than hardcoded
    if _cache["rate"] is not None:
        logger.warning("⚠️ Using stale BACEN cache (API unreachable). Retrying in 5 minutes.")
        _cache["fetched_at"] = now - _CACHE_TTL_SECONDS + 300
        return _cache["rate"]

    # 4. Ultimate fallback — .env value
    logger.warning(f"⚠️ BACEN unavailable. Using .env fallback: R$ {settings.FALLBACK_USD_TO_BRL}. Retrying in 5 minutes.")
    _cache["rate"] = settings.FALLBACK_USD_TO_BRL
    _cache["fetched_at"] = now - _CACHE_TTL_SECONDS + 300
    return settings.FALLBACK_USD_TO_BRL

