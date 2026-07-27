import json
import httpx

from llm_service.llm_clients.llm_client import LLMClient

class OllamaClient(LLMClient):
    models = {
        'qwen2.5-coder:1.5b': {
            'model_name': 'qwen2.5-coder:1.5b',
            'host': '127.0.0.1',
            'port': 11434,
            'endpoint': 'http://127.0.0.1:11434',
        },
        'qwen3:8b': {
            'model_name': 'qwen3:8b',
            'host': '127.0.0.1',
            'port': 11434,
            'endpoint': 'http://127.0.0.1:11434',
        },
    }
    def __init__(self, model_name: str):
        if model_name not in self.models:
            raise ValueError(f"LLM model '{model_name}' is not supported.")
        self.model_name = model_name

    async def chat(
        self,
        system_instructions: str,
        prompt: str,
        response_format: str | dict[str, any]=None,
        **kwargs,
    ):
        options = kwargs.get('options', { 'temperature': 0.0 })

        body = {
            'model': self.model_name,
            'format': response_format,
            'options': options,
            'stream': False,
            'messages': [
                {
                    'role': 'system',
                    'content': system_instructions,
                },
                {
                    'role': 'user',
                    'content': prompt,
                }
            ],
        }

        response = await httpx.AsyncClient(timeout=None).post(
            f'{self.models[self.model_name]['endpoint']}/api/chat',
            json=body,
        )

        response.raise_for_status()
        data = response.json()
        content = data['message']['content']
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Return raw text if JSON decoding fails
            # Note: this is a temporary solution.
            return content