from fastapi import FastAPI, Body, Query
import uvicorn

from llm_service.llm_selector import LLMSelector

from common.config import services
from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan
from common.schemas.UpdateManifestRequest import UpdateManifestRequest

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

@app.post("/get-update-plan")
async def get_update_plan(
    update_context: ManifestFileUpdateContext = Body(...),
    model_name: str | None = Query(None)
) -> ManifestFileUpdatePlan:
    model = LLMSelector.get_llm_model(model_name)
    return await model.get_update_plan(update_context)

@app.post("/update-manifest")
async def update_manifest(
    request: UpdateManifestRequest = Body(...),
    model_name: str | None = Query(None)
) -> File:
    model = LLMSelector.get_llm_model(model_name)
    return await model.update_manifest(request.manifest_file, request.update_plan)


def main() -> None:
    uvicorn.run(
        app,
        host=services['llm-service']['host'],
        port=services['llm-service']['port'],
    )