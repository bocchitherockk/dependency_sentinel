import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Body, Query
from fastapi import HTTPException

from common.schemas.DependencyUpdateContext import DependencyUpdateContext
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan
from common.schemas.UpdateManifestRequest import UpdateManifestRequest

from llm_service.llm_selector import LLMSelector
from llm_service.events.ManifestFilesDetectedEventProducer import ManifestFilesDetectedEventProducer
from llm_service.events.RepositoryFilesListRetrievedEventConsumer import RepositoryFilesListRetrievedEventConsumer
from llm_service.events.DependenciesExtractedEventProducer import DependenciesExtractedEventProducer
from llm_service.events.ManifestFilesContentRetrievedEventConsumer import ManifestFilesContentRetrievedEventConsumer
from llm_service.exceptions.LLMModelNotFoundException import LLMModelNotFoundException
from llm_service.exceptions.LLMRequestException import LLMRequestException
from llm_service.exceptions.ToolCallException import ToolCallException
from llm_service.exceptions.MCPListToolsException import MCPListToolsException


manifest_files_detected_event_producer: ManifestFilesDetectedEventProducer = ManifestFilesDetectedEventProducer()
repository_files_list_retrieved_event_consumer: RepositoryFilesListRetrievedEventConsumer = RepositoryFilesListRetrievedEventConsumer(manifest_files_detected_event_producer)
dependencies_extracted_event_producer: DependenciesExtractedEventProducer = DependenciesExtractedEventProducer()
manifest_files_content_retrieved_event_consumer: ManifestFilesContentRetrievedEventConsumer = ManifestFilesContentRetrievedEventConsumer(dependencies_extracted_event_producer)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await manifest_files_detected_event_producer.start()
    await repository_files_list_retrieved_event_consumer.start()
    await dependencies_extracted_event_producer.start()
    await manifest_files_content_retrieved_event_consumer.start()

    repository_files_list_retrieved_event_consumer_task = asyncio.create_task(
        repository_files_list_retrieved_event_consumer.consume()
    )
    manifest_files_content_retrieved_event_consumer_task = asyncio.create_task(
        manifest_files_content_retrieved_event_consumer.consume()
    )

    yield

    repository_files_list_retrieved_event_consumer_task.cancel()
    manifest_files_content_retrieved_event_consumer_task.cancel()

    await manifest_files_detected_event_producer.stop()
    await repository_files_list_retrieved_event_consumer.stop()
    await dependencies_extracted_event_producer.stop()
    await manifest_files_content_retrieved_event_consumer.stop()


app = FastAPI(
    title='LLM Service',
    description='Service responsible for interacting with LLM models',
    version='0.1.0',
    lifespan=lifespan,
)


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
