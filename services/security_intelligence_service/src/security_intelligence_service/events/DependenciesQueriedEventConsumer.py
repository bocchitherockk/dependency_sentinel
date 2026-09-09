from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from events.consumer import EventConsumer
from events.config import KafkaConfig
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent
from events.schemas.ManifestFilesEditedEvent import ManifestFilesEditedEvent

from security_intelligence_service.events.ManifestFilesEditedEventProducer import ManifestFilesEditedEventProducer
from security_intelligence_service.utils import analyze_update_context_and_update_manifests

logger: Logger = get_global_logger(__name__)

class DependenciesQueriedEventConsumer(EventConsumer):
    def __init__(self, manifest_files_edited_event_producer: ManifestFilesEditedEventProducer):
        self.manifest_files_edited_event_producer: ManifestFilesEditedEventProducer = manifest_files_edited_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_DEPENDENCIES_QUERIED,
            group_id=KafkaConfig.CONSUMER_GROUP_SECURITY_INTELLIGENCE_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        dependencies_queried_event: DependenciesQueriedEvent = DependenciesQueriedEvent(**value)
        logger.info(f"Received DependenciesQueriedEvent for repository '{dependencies_queried_event.repository_name}' owned by '{dependencies_queried_event.repository_owner_name}'.")
        logger.debug(f'DependenciesQueriedEvent details: {dependencies_queried_event}')

        repository_name: str = dependencies_queried_event.repository_name
        repository_owner_name: str = dependencies_queried_event.repository_owner_name
        manifest_files_update_context: list[ManifestFileUpdateContext] = dependencies_queried_event.manifest_files_update_context

        branch_name, summary = await analyze_update_context_and_update_manifests(
            repository_name,
            manifest_files_update_context,
        )
        manifest_files_edited_event: ManifestFilesEditedEvent = ManifestFilesEditedEvent(
            key=repository_name,
            repository_url=dependencies_queried_event.repository_url,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=dependencies_queried_event.default_branch,
            update_branch=branch_name,
            summary=summary,
        )
        await self.manifest_files_edited_event_producer.publish(event=manifest_files_edited_event)
        logger.info(f"Published ManifestFilesEditedEvent for repository '{repository_name}' owned by '{repository_owner_name}' with update branch '{branch_name}'.")
        logger.debug(f'ManifestFilesEditedEvent details: {manifest_files_edited_event}')
