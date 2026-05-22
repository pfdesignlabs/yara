from functools import lru_cache

from langchain_openai import ChatOpenAI


@lru_cache
def get_chat_model() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4.1-mini", temperature=0.2)
