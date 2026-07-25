from fastapi import FastAPI

from llm_service.ollama_provider import chat
from llm_service.prompts import (
    MANIFEST_DETECTION_PROMPT,
    DEPENDENCY_EXTRACTION_PROMPT,
)

app = FastAPI()


@app.post("/detect-manifests")
async def detect_manifests(files: list[str]):

    prompt = (
        MANIFEST_DETECTION_PROMPT
        + "\n\n"
        + "\n".join(files)
    )

    return await chat(prompt)


@app.post("/extract-dependencies")
async def extract_dependencies(content: str):

    prompt = (
        DEPENDENCY_EXTRACTION_PROMPT
        + "\n\n"
        + content
    )

    return await chat(prompt)