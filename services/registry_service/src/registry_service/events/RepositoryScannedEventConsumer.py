import asyncio
from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.ManifestFile import ManifestFile
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext
from events.config import KafkaConfig
from events.consumer import EventConsumer
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent
from events.schemas.DependenciesQueriedEvent import DependenciesQueriedEvent

from registry_service.events.DependenciesQueriedEventProducer import DependenciesQueriedEventProducer
from registry_service.utils import get_manifest_file_update_context

logger: Logger = get_global_logger(__name__)


class RepositoryScannedEventConsumer(EventConsumer):
    def __init__(self, dependencies_queried_event_producer: DependenciesQueriedEventProducer):
        self.dependencies_queried_event_producer: DependenciesQueriedEventProducer = dependencies_queried_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_REPOSITORY_SCANNED,
            group_id=KafkaConfig.CONSUMER_GROUP_REGISTRY_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        repository_scanned_event: RepositoryScannedEvent = RepositoryScannedEvent(**value)
        logger.info(f"Received RepositoryScannedEvent for repository '{repository_scanned_event.repository_name}'.")
        logger.debug(f"RepositoryScannedEvent details: {repository_scanned_event}")

        repository_name: str = repository_scanned_event.repository_name
        repository_owner_name: str = repository_scanned_event.repository_owner_name
        current_manifest_files: list[ManifestFile] = repository_scanned_event.detected_manifest_files

        manifest_files_update_context: list[ManifestFileUpdateContext] = await asyncio.gather(*[
            get_manifest_file_update_context(manifest_file)
            for manifest_file in current_manifest_files
        ])

        dependencies_queried_event: DependenciesQueriedEvent = DependenciesQueriedEvent(
            key=repository_name,
            repository_url=repository_scanned_event.repository_url,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=repository_scanned_event.default_branch,
            manifest_files_update_context=manifest_files_update_context,
        )
        await self.dependencies_queried_event_producer.publish(event=dependencies_queried_event)
        logger.info(f"DependenciesQueriedEvent published for repository '{repository_name}'.")
        logger.debug(f"DependenciesQueriedEvent details: {dependencies_queried_event}")
