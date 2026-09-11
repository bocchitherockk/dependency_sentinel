from logging import Logger

from common.logging.global_logger import get_global_logger
from common.schemas.ManifestFile import ManifestFile
from events.config import KafkaConfig
from events.consumer import EventConsumer
from events.schemas.ManifestFilesContentRetrievedEvent import ManifestFilesContentRetrievedEvent
from events.schemas.DependenciesExtractedEvent import DependenciesExtractedEvent

from llm_service.events.DependenciesExtractedEventProducer import DependenciesExtractedEventProducer
from llm_service.utils import extract_dependencies


logger: Logger = get_global_logger(__name__)

class ManifestFilesContentRetrievedEventConsumer(EventConsumer):
    def __init__(self, dependencies_extracted_event_producer: DependenciesExtractedEventProducer):
        self.dependencies_extracted_event_producer: DependenciesExtractedEventProducer = dependencies_extracted_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_MANIFEST_FILES_CONTENT_RETRIEVED,
            group_id=KafkaConfig.CONSUMER_GROUP_LLM_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        manifest_files_content_retrieved_event: ManifestFilesContentRetrievedEvent = ManifestFilesContentRetrievedEvent(**value)
        logger.info(f'Received ManifestFilesContentRetrievedEvent for repository: {manifest_files_content_retrieved_event.repository_name}')
        logger.debug(f'ManifestFilesContentRetrievedEvent details: {manifest_files_content_retrieved_event}')

        manifest_files: list[ManifestFile] = await extract_dependencies(manifest_files_content_retrieved_event.manifest_files)
        dependencies_extracted_event: DependenciesExtractedEvent = DependenciesExtractedEvent(
            key=manifest_files_content_retrieved_event.repository_name,
            repository_url=manifest_files_content_retrieved_event.repository_url,
            repository_name=manifest_files_content_retrieved_event.repository_name,
            repository_owner_name=manifest_files_content_retrieved_event.repository_owner_name,
            default_branch=manifest_files_content_retrieved_event.default_branch,
            manifest_files=manifest_files,
        )
        logger.info(f'Publishing DependenciesExtractedEvent for repository: {dependencies_extracted_event.key}')
        logger.debug(f'DependenciesExtractedEvent details: {dependencies_extracted_event}')
        await self.dependencies_extracted_event_producer.publish(dependencies_extracted_event)
