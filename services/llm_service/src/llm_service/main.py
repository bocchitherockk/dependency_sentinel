from fastapi import FastAPI, Body, Query
import uvicorn

from llm_service.llm_selector import LLMSelector

from common.config import services
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile

app = FastAPI()


@app.post("/detect-manifests")
async def detect_manifests(
    files: list[File] = Body(...),
    model_name: str | None = Query(None)
) -> list[File]:
    model = LLMSelector.get_llm_model(model_name)
    return await model.detect_manifests(files)

@app.post("/extract-dependencies")
async def extract_dependencies(
    manifest_file: File = Body(...),
    model_name: str | None = Query(None)
) -> ManifestFile:
    model = LLMSelector.get_llm_model(model_name)
    return await model.extract_dependencies(manifest_file)

@app.post("/analyze-security-delta")
async def analyze_security_delta(
    update_context: dict = Body(...),
    model_name: str | None = Query(None)
) -> dict:
    model = LLMSelector.get_llm_model(model_name)
    return await model.analyze_security_delta(update_context)


def main() -> None:
    uvicorn.run(
        app,
        host=services['llm-service']['host'],
        port=services['llm-service']['port'],
    )