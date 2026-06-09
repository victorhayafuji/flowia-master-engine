"""Chat LLM factory — OpenAI via LangChain."""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from packages.auth_core.config import settings


@lru_cache(maxsize=4)
def get_chat_llm(*, temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.MODEL_NAME,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
    )
