import asyncio
from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan
from events.consumer import EventConsumer
from events.config import KafkaConfig
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from events.schemas.ManifestFilesEditedEvent import ManifestFilesEditedEvent

from llm_service.events.ManifestFilesEditedEventProducer import ManifestFilesEditedEventProducer
from llm_service.utils import (
    get_manifest_files_update_plan,
    update_manifest_file,
)


logger: Logger = get_global_logger(__name__)

class DependenciesQueriedEventConsumer(EventConsumer):
    def __init__(self, manifest_files_edited_event_producer: ManifestFilesEditedEventProducer):
        self.manifest_files_edited_event_producer: ManifestFilesEditedEventProducer = manifest_files_edited_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_DEPENDENCIES_QUERIED,
            group_id=KafkaConfig.CONSUMER_GROUP_LLM_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        dependencies_queried_event: DependenciesQueriedEvent = DependenciesQueriedEvent(**value)
        logger.info(f"Received DependenciesQueriedEvent for repository '{dependencies_queried_event.repository_name}' owned by '{dependencies_queried_event.repository_owner_name}'.")
        logger.debug(f'DependenciesQueriedEvent details: {dependencies_queried_event.model_dump_json(indent=2)}')

        repository_name: str = dependencies_queried_event.repository_name
        repository_owner_name: str = dependencies_queried_event.repository_owner_name
        manifest_files_update_context: list[ManifestFileUpdateContext] = dependencies_queried_event.manifest_files_update_context

        manifest_files_update_plan: list[ManifestFileUpdatePlan] = await get_manifest_files_update_plan(manifest_files_update_context)

        # Clean up the update plans to remove any dependencies that don't actually need updates
        for manifest_file_update_plan in manifest_files_update_plan:
            manifest_file_update_plan.remove_unnecessary_dependency_update_elements()

        # Remove any manifest files that have no updates after cleaning
        manifest_files_update_plan = [
            manifest_file_update_plan
            for manifest_file_update_plan in manifest_files_update_plan
            if manifest_file_update_plan.has_updates()
        ]

        if not manifest_files_update_plan:
            logger.info(f"No updates needed for repository '{repository_name}'. No branch created, no files modified.")
        else:
            logger.info(f"Updates needed for repository '{repository_name}'. Proceeding to create a new branch and update manifest files.")
            logger.debug(f'ManifestFileUpdatePlans details: {[manifest_file_update_plan.model_dump_json(indent=2) for manifest_file_update_plan in manifest_files_update_plan]}')

        reasonings: list[str] = await asyncio.gather(*[
            update_manifest_file(manifest_file_update_plan)
            for manifest_file_update_plan in manifest_files_update_plan
        ])

        has_updates: bool = bool(manifest_files_update_plan)

        updates_summary: str = ''
        for manifest_file_update_plan, reasoning in zip(manifest_files_update_plan, reasonings):
            cleaned_reasoning: str = reasoning.strip('"').replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
            updates_summary += f"# file: {manifest_file_update_plan.path}\n"
            updates_summary += f"Reasoning:\n{cleaned_reasoning}\n"
            updates_summary += "───────────────────────────────────────────\n"

        manifest_files_edited_event: ManifestFilesEditedEvent = ManifestFilesEditedEvent(
            key=repository_name,
            repository_url=dependencies_queried_event.repository_url,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=dependencies_queried_event.default_branch,
            has_updates=has_updates,
            updates_summary=updates_summary,
        )
        await self.manifest_files_edited_event_producer.publish(event=manifest_files_edited_event)
        logger.info(f"Published ManifestFilesEditedEvent for repository '{repository_name}'.")
        logger.debug(f'ManifestFilesEditedEvent details: {manifest_files_edited_event.model_dump_json(indent=2)}')
