import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))


async def chat(prompt: str) -> dict:
    response = await httpx.AsyncClient(timeout=OLLAMA_TIMEOUT_SECONDS).post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        },
    )

    response.raise_for_status()

    data = response.json()

    content = data["message"]["content"]

    return json.loads(content)