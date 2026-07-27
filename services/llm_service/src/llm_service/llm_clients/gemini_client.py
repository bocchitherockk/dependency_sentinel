import json
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

from llm_service.llm_clients.llm_client import LLMClient

class GeminiClient(LLMClient):
    def __init__(self, model_name: str):
        self.model_name = model_name

    async def chat(
        self,
        system_instructions: str,
        prompt: str,
        response_format: str | dict[str, any]=None,
        **kwargs,
    ):
        client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

        interaction = client.interactions.create(
            model=self.model_name,
            input=system_instructions + prompt,
            response_format=response_format,
        )

        try:
            return json.loads(interaction.output_text)
        except json.JSONDecodeError:
            # Return raw text if JSON decoding fails
            # Note: this is a temporary solution.
            return interaction.output_text
