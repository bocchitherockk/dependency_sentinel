from fastapi import FastAPI, Body, Query
from fastapi import HTTPException

from llm_service.llm_selector import LLMSelector

from common.schemas.File import File
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan
from common.schemas.UpdateManifestRequest import UpdateManifestRequest

from llm_service.exceptions.LLMModelNotFoundException import LLMModelNotFoundException
from llm_service.exceptions.LLMRequestException import LLMRequestException
from llm_service.exceptions.ToolCallException import ToolCallException
from llm_service.exceptions.MCPListToolsException import MCPListToolsException

app = FastAPI()


@app.post("/detect-manifests")
async def detect_manifests(
    files: list[File] = Body(...),
    model_name: str | None = Query(None)
) -> list[File]:
    try:
        model = LLMSelector.get_llm_model(model_name)
        return await model.detect_manifests(files)
    except LLMModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (LLMRequestException, ToolCallException, MCPListToolsException) as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-dependencies")
async def extract_dependencies(
    manifest_file: File = Body(...),
    model_name: str | None = Query(None)
) -> ManifestFile | None:
    try:
        model = LLMSelector.get_llm_model(model_name)
        return await model.extract_dependencies(manifest_file)
    except LLMModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (LLMRequestException, ToolCallException, MCPListToolsException) as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-update-plan")
async def get_update_plan(
    dependency_update_context: DependencyUpdateContext = Body(...),
    model_name: str | None = Query(None)
) -> DependencyUpdatePlan:
    try:
        model = LLMSelector.get_llm_model(model_name)
        return await model.get_update_plan(dependency_update_context)
    except LLMModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (LLMRequestException, ToolCallException, MCPListToolsException) as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update-manifest")
async def update_manifest(
    request: UpdateManifestRequest = Body(...),
    model_name: str | None = Query(None)
) -> str:
    try:
        model = LLMSelector.get_llm_model(model_name)
        return await model.update_manifest(request.manifest_file, request.update_plan)
    except LLMModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (LLMRequestException, ToolCallException, MCPListToolsException) as e:
        raise HTTPException(status_code=500, detail=str(e))
