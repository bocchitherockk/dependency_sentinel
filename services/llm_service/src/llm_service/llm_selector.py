from llm_service.llm_clients.llm_client import LLMClient
from llm_service.llm_clients.ollama_client import OllamaClient
from llm_service.llm_clients.gemini_client import GeminiClient

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
            raise ValueError(f"LLM model '{model_name}' is not supported.")
        return LLMSelector.llm_clients[model_name]
