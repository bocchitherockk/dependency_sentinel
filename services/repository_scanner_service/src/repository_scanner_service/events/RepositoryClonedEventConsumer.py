from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.ManifestFile import ManifestFile
from events.consumer import EventConsumer
from events.config import KafkaConfig
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent
from events.schemas.RepositoryScannedEvent import RepositoryScannedEvent

from repository_scanner_service.events.RepositoryScannedEventProducer import RepositoryScannedEventProducer
from repository_scanner_service.utils import scan_repository

logger: Logger = get_global_logger(__name__)


class RepositoryClonedEventConsumer(EventConsumer):
    def __init__(self, repository_scanned_event_producer: RepositoryScannedEventProducer):
        self.repository_scanned_event_producer: RepositoryScannedEventProducer = repository_scanned_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_REPOSITORY_CLONED,
            group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_SCANNER_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        repository_cloned_event: RepositoryClonedEvent = RepositoryClonedEvent(**value)
        logger.info(f"Received RepositoryClonedEvent for repository '{repository_cloned_event.repository_name}'.")
        logger.debug(f"RepositoryClonedEvent details: {repository_cloned_event}")

        repository_name = repository_cloned_event.repository_name
        repository_owner_name = repository_cloned_event.repository_owner_name
        if not repository_name:
            logger.error("Repository name cannot be empty.")
            raise ValueError("Repository name cannot be empty.")

        try:
            detected_manifest_files: list[ManifestFile] = await scan_repository(repository_name)
            repository_scanned_event: RepositoryScannedEvent = RepositoryScannedEvent(
                repository_url=repository_cloned_event.repository_url,
                repository_name=repository_name,
                repository_owner_name=repository_owner_name,
                default_branch=repository_cloned_event.default_branch,
                detected_manifest_files=detected_manifest_files,
                key=repository_name
            )
            await self.repository_scanned_event_producer.publish(event=repository_scanned_event)
            logger.info(f"RepositoryScannedEvent published for repository '{repository_name}'.")
            logger.debug(f"RepositoryScannedEvent details: {repository_scanned_event}")
        except Exception as error:
            logger.error(f"Repository scan failed for repository '{repository_name}': {error}")
            raise ValueError(f"Repository scan failed: {error}") from error
