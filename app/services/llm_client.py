"""
LLM 客户端模块
- 封装 DeepSeek（OpenAI 兼容接口）
- 单例模式，全局复用同一 ChatOpenAI 实例
- 对外暴露 get_llm()
"""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.core.logger import setup_logger

logger = setup_logger("patent_agent.llm")


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """
    返回全局 LLM 实例（线程安全，lru_cache 保证单例）。
    streaming=True 使 astream_events 能捕获 on_chat_model_stream 事件。
    """
    settings = get_settings()
    logger.info(
        f"Initializing LLM | model={settings.llm_model_name} "
        f"max_tokens={settings.deepseek_max_tokens} "
        f"temperature={settings.deepseek_temperature}"
    )
    return ChatOpenAI(
        model=settings.llm_model_name,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        max_tokens=settings.deepseek_max_tokens,
        temperature=settings.deepseek_temperature,
        streaming=True,
        request_timeout=120,
    )