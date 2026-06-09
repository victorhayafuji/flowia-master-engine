"""Shared OpenAI client helpers for chat, embeddings and vision OCR."""
from __future__ import annotations

import base64
import logging
from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from packages.auth_core.config import settings

logger = logging.getLogger(__name__)

_OCR_PROMPT = (
    "Extraia todo o texto deste documento em Markdown estruturado. "
    "Preserve tabelas, listas e valores exatos."
)
_IMAGE_OCR_PROMPT = (
    "Extraia todo o texto desta imagem em Markdown estruturado. "
    "Preserve tabelas, listas e valores exatos."
)


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


@lru_cache(maxsize=1)
def get_async_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def embed_text(text: str) -> list[float]:
    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL_NAME,
        input=text,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


async def embed_text_async(text: str) -> list[float]:
    client = get_async_openai_client()
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL_NAME,
        input=text,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


async def generate_text_async(prompt: str, *, model: str | None = None) -> str:
    client = get_async_openai_client()
    response = await client.chat.completions.create(
        model=model or settings.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return (response.choices[0].message.content or "").strip()


async def extract_document_text_async(
    file_bytes: bytes,
    mime_type: str,
    file_name: str,
) -> str:
    """OCR / text extraction via OpenAI vision models."""
    client = get_async_openai_client()
    b64 = base64.standard_b64encode(file_bytes).decode("ascii")

    if mime_type.startswith("image/"):
        content: list[dict] = [
            {"type": "text", "text": _IMAGE_OCR_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        ]
    elif mime_type == "application/pdf":
        content = [
            {"type": "text", "text": _OCR_PROMPT},
            {
                "type": "file",
                "file": {
                    "filename": file_name or "document.pdf",
                    "file_data": f"data:application/pdf;base64,{b64}",
                },
            },
        ]
    else:
        content = [
            {"type": "text", "text": _OCR_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        ]

    try:
        response = await client.chat.completions.create(
            model=settings.VISION_MODEL_NAME,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception("OpenAI vision OCR failed for %s (%s)", file_name, mime_type)
        raise
