from datetime import datetime, timezone
from logging import Logger
import os
from pathlib import Path

from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger
from events.consumer import EventConsumer
from events.config import KafkaConfig
from events.schemas.ManifestFilesEditedEvent import ManifestFilesEditedEvent
from events.schemas.ScanCompletedEvent import ScanCompletedEvent

from repository_storage_service.events.ScanCompletedEventProducer import ScanCompletedEventProducer
from repository_storage_service.config import REPOSITORIES_PATH

from repository_storage_service.utils import (
    create_git_branch,
    commit_and_push_changes,
    create_pull_request,
)

logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info('Environment variables loaded from .env file.')
logger.debug('Environment variables: ')
logger.debug(f'GITHUB_PERSONAL_ACCESS_TOKEN: {os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")}')


class ManifestFilesEditedEventConsumer(EventConsumer):
    def __init__(self, scan_completed_event_producer: ScanCompletedEventProducer):
        self.scan_completed_event_producer: ScanCompletedEventProducer = scan_completed_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_MANIFEST_FILES_EDITED,
            group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        manifest_files_edited_event: ManifestFilesEditedEvent = ManifestFilesEditedEvent(**value)
        logger.info(f'Received ManifestFilesEditedEvent for repository: {manifest_files_edited_event.repository_name}')
        logger.debug(f'ManifestFilesEditedEvent details: {manifest_files_edited_event}')
        if not manifest_files_edited_event.has_updates:
            # If `has_updates` is false, it means that no manifest file was modified
            # so we don't need to create a branch, commit any changes or create a pull request.
            logger.info(f'No changes to commit for repository: {manifest_files_edited_event.repository_name}')
            return

        repository_name: str = manifest_files_edited_event.repository_name
        repository_owner_name: str = manifest_files_edited_event.repository_owner_name
        destination: Path = REPOSITORIES_PATH / repository_name

        timestamp: str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
        new_branch_name: str = f'dependency-sentinel/update-{timestamp}'
        create_git_branch(repository_name, new_branch_name)

        commit_and_push_changes(destination)
        create_pull_request(
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=manifest_files_edited_event.default_branch,
            branch_name=new_branch_name,
            body=manifest_files_edited_event.updates_summary
        )

        scan_completed_event: ScanCompletedEvent = ScanCompletedEvent(
            key=repository_name,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
        )
        logger.info(f'Publishing ScanCompletedEvent for repository: {repository_name}')
        logger.debug(f'ScanCompletedEvent details: {scan_completed_event}')
        print('################### FINISHED ###################')
        await self.scan_completed_event_producer.publish(event=scan_completed_event)
