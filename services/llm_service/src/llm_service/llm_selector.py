from logging import Logger

from common.logging.global_logger import get_global_logger

from llm_service.llm_clients.llm_client import LLMClient
from llm_service.llm_clients.ollama_client import OllamaClient
from llm_service.llm_clients.gemini_client import GeminiClient

logger: Logger = get_global_logger(__name__)

class LLMSelector:

    llm_clients: dict[str, LLMClient] = {
        'qwen2.5-coder:1.5b':    OllamaClient('qwen2.5-coder:1.5b'),
        'qwen3:8b':              OllamaClient('qwen3:8b'),
        'gemini-3.5-flash':      GeminiClient('gemini-3.5-flash'),
        'gemini-3.5-flash-lite': GeminiClient('gemini-3.5-flash-lite'),
        'gemini-3.6-flash':      GeminiClient('gemini-3.6-flash'),
        'default':               OllamaClient('qwen2.5-coder:1.5b'),
    }

    @staticmethod
    def get_llm_model(model_name: str | None) -> LLMClient:
        if model_name is None:
            model_name = 'default'
        if model_name not in LLMSelector.llm_clients:
            logger.error(f"LLM model '{model_name}' is not supported.")
            raise ValueError(f"LLM model '{model_name}' is not supported.")
        return LLMSelector.llm_clients[model_name]

logger.info(f'LLMSelector initialized with models: {list(LLMSelector.llm_clients.keys())}')
