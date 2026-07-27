from typing import Any
from fastapi import FastAPI, Body, Query
import uvicorn

from common.config import services
from llm_service.llm_selector import LLMSelector


app = FastAPI()


@app.post("/detect-manifests")
async def detect_manifests(
    files: list[str] = Body(...),
    model_name: str | None = Query(None)
):
    model = LLMSelector.get_llm_model(model_name)
    return await model.detect_manifests(files)

@app.post("/extract-dependencies")
async def extract_dependencies(
    manifest_file: dict[str, Any] = Body(...),
    model_name: str | None = Query(None)
):
    model = LLMSelector.get_llm_model(model_name)
    return await model.extract_dependencies(manifest_file)

def main() -> None:
    uvicorn.run(
        app,
        host=services['llm-service']['host'],
        port=services['llm-service']['port'],
    )