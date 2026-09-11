from logging import Logger

from common.logging.global_logger import get_global_logger
from events.config import KafkaConfig
from events.consumer import EventConsumer
from events.schemas.RepositoryFilesListRetrievedEvent import RepositoryFilesListRetrievedEvent
from events.schemas.ManifestFilesDetectedEvent import ManifestFilesDetectedEvent

from llm_service.events.ManifestFilesDetectedEventProducer import ManifestFilesDetectedEventProducer
from llm_service.utils import detect_manifest_files


logger: Logger = get_global_logger(__name__)

class RepositoryFilesListRetrievedEventConsumer(EventConsumer):
    def __init__(self, manifest_files_detected_event_producer: ManifestFilesDetectedEventProducer):
        self.manifest_files_detected_event_producer: ManifestFilesDetectedEventProducer = manifest_files_detected_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_REPOSITORY_FILES_LIST_RETRIEVED,
            group_id=KafkaConfig.CONSUMER_GROUP_LLM_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        repository_files_list_retrieved_event: RepositoryFilesListRetrievedEvent = RepositoryFilesListRetrievedEvent(**value)
        logger.info(f'Received RepositoryFilesListRetrievedEvent for repository: {repository_files_list_retrieved_event.repository_name}')
        logger.debug(f'RepositoryFilesListRetrievedEvent details: {repository_files_list_retrieved_event}')

        detected_manifest_files = await detect_manifest_files(repository_files_list_retrieved_event.retrieved_repository_files_list)

        manifest_files_detected_event: ManifestFilesDetectedEvent = ManifestFilesDetectedEvent(
            key=repository_files_list_retrieved_event.repository_name,
            repository_url=repository_files_list_retrieved_event.repository_url,
            repository_name=repository_files_list_retrieved_event.repository_name,
            repository_owner_name=repository_files_list_retrieved_event.repository_owner_name,
            default_branch=repository_files_list_retrieved_event.default_branch,
            detected_manifest_files=detected_manifest_files
        )
        logger.info(f'Publishing ManifestFilesDetectedEvent for repository: {manifest_files_detected_event.key}')
        logger.debug(f'ManifestFilesDetectedEvent details: {manifest_files_detected_event}')
        await self.manifest_files_detected_event_producer.publish(manifest_files_detected_event)
