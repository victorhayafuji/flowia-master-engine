"""Shared helpers for the Data Lake medallion pipeline."""
import hashlib
import re
from typing import Any

EMBEDDING_DIM = 768
BRONZE_BUCKET = "bronze_raw"
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/markdown",
}


def normalize_embedding(values: list[float], target_dim: int = EMBEDDING_DIM) -> list[float]:
    if len(values) == target_dim:
        return values
    if len(values) > target_dim:
        return values[:target_dim]
    return values + [0.0] * (target_dim - len(values))


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, min_len: int = 10, large_chunk_threshold: int = 400) -> list[str]:
    """Splits cleaned text into embeddable chunks for the Gold layer."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = [c.strip() for c in normalized.split("\n\n") if len(c.strip()) > min_len]

    if len(chunks) == 1 and len(chunks[0]) > large_chunk_threshold:
        chunks = [ln.strip() for ln in chunks[0].split("\n") if len(ln.strip()) > min_len]

    return chunks


def content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def normalize_search_content(content: str) -> str:
    text = content.lower().strip()
    text = re.sub(r"[*#_\-\[\]]", "", text)
    return re.sub(r"\s+", " ", text)


def dedupe_search_results(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Removes results with identical normalized content, keeping highest similarity."""
    sorted_results = sorted(
        results,
        key=lambda r: r.get("similarity", 0),
        reverse=True,
    )
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in sorted_results:
        key = normalize_search_content(row.get("content", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped
