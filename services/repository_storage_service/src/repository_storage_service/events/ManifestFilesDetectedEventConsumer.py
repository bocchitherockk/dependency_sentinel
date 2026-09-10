from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.File import File
from events.config import KafkaConfig
from events.consumer import EventConsumer
from events.schemas.ManifestFilesDetectedEvent import ManifestFilesDetectedEvent
from events.schemas.ManifestFilesContentRetrievedEvent import ManifestFilesContentRetrievedEvent

from repository_storage_service.events.ManifestFilesContentRetrievedEventProducer import ManifestFilesContentRetrievedEventProducer
from repository_storage_service.utils import retrieve_manifest_files_content

logger: Logger = get_global_logger(__name__)

class ManifestFilesDetectedEventConsumer(EventConsumer):
    def __init__(self, manifest_files_content_retrieved_event_producer: ManifestFilesContentRetrievedEventProducer):
        self.manifest_files_content_retrieved_event_producer: ManifestFilesContentRetrievedEventProducer = manifest_files_content_retrieved_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_MANIFEST_FILES_DETECTED,
            group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        manifest_files_detected_event: ManifestFilesDetectedEvent = ManifestFilesDetectedEvent(**value)
        logger.info(f'Received ManifestFilesDetectedEvent for repository: {manifest_files_detected_event.repository_name}')
        logger.debug(f'ManifestFilesDetectedEvent details: {manifest_files_detected_event}')

        manifest_files: list[File] = retrieve_manifest_files_content(manifest_files_detected_event.detected_manifest_files)

        manifest_files_content_retrieved_event: ManifestFilesContentRetrievedEvent = ManifestFilesContentRetrievedEvent(
            repository_url=manifest_files_detected_event.repository_url,
            repository_name=manifest_files_detected_event.repository_name,
            repository_owner_name=manifest_files_detected_event.repository_owner_name,
            default_branch=manifest_files_detected_event.default_branch,
            manifest_files=manifest_files,
        )
        logger.info(f'Publishing ManifestFilesContentRetrievedEvent for repository: {manifest_files_detected_event.repository_name}')
        logger.debug(f'ManifestFilesContentRetrievedEvent details: {manifest_files_content_retrieved_event}')
        await self.manifest_files_content_retrieved_event_producer.publish(manifest_files_content_retrieved_event)
