from logging import Logger
import os
from pathlib import Path

from git import Repo
from github import Github
from dotenv import load_dotenv

from common.logging.global_logger import get_global_logger
from events.consumer import EventConsumer
from events.config import KafkaConfig
from events.schemas.ManifestFilesEditedEvent import ManifestFilesEditedEvent
from events.schemas.ScanCompletedEvent import ScanCompletedEvent

from repository_storage_service.events.ScanCompletedEventProducer import ScanCompletedEventProducer
from repository_storage_service.config import REPOSITORIES_PATH

logger: Logger = get_global_logger(__name__)

load_dotenv()
logger.info('Environment variables loaded from .env file.')
logger.debug('Environment variables: ')
logger.debug(f'GITHUB_PERSONAL_ACCESS_TOKEN: {os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")}')


def commit_and_push_changes(repository_path: Path) -> None:
    if not repository_path.exists():
        logger.error(f"The repository path '{repository_path}' does not exist.")
        raise FileNotFoundError(f"The repository path '{repository_path}' does not exist.")

    repo = Repo(repository_path)
    repo.git.add(A=True)  # Stage all changes
    repo.index.commit('Update manifest files')
    current_branch = repo.active_branch.name

    github_access_token = os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN')
    remote_url = repo.remotes.origin.url.replace('www.github.com', 'github.com') # we remove the 'www' prefix because it can cause issues with authentication (github am i right ??, billion dollar company)
    if remote_url.startswith('https://') and '@' not in remote_url and github_access_token:
        auth_url = remote_url.replace('https://', f'https://{github_access_token}:@')
        repo.git.push(auth_url, f'{current_branch}:{current_branch}')
    else:
        repo.git.push('origin', current_branch)

    logger.info(f"Changes committed and pushed for repository at '{repository_path}' on branch '{current_branch}'.")

def create_pull_request(
    repository_name: str,
    repository_owner_name: str,
    default_branch: str,
    branch_name: str,
    body: str
) -> None:
    github_access_token: str = os.getenv('GITHUB_PERSONAL_ACCESS_TOKEN')
    g = Github(github_access_token)

    repo = g.get_repo(f'{repository_owner_name}/{repository_name}')

    pull_request = repo.create_pull(
        title='Dependency Sentinel auto update dependencies',
        base=default_branch,
        head=branch_name,
        body=body,
    )
    logger.info(f"Pull request created for repository '{repository_name}' on branch '{branch_name}'.")
    logger.debug(f"Pull request URL: {pull_request.html_url}")


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
        if manifest_files_edited_event.summary is None:
            # If the summary is empty, it means that no manifest file was modified
            # and a git branch was not created
            # so we don't need to commit any changes or create a pull request.
            logger.info(f'No changes to commit for repository: {manifest_files_edited_event.repository_name}')
            return

        repository_name: str = manifest_files_edited_event.repository_name
        repository_owner_name: str = manifest_files_edited_event.repository_owner_name
        destination: Path = REPOSITORIES_PATH / repository_name

        commit_and_push_changes(destination)
        create_pull_request(
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=manifest_files_edited_event.default_branch,
            branch_name=manifest_files_edited_event.update_branch,
            body=manifest_files_edited_event.summary
        )

        scan_completed_event: ScanCompletedEvent = ScanCompletedEvent(
            key=repository_name,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
        )
        logger.info(f'Publishing ScanCompletedEvent for repository: {repository_name}')
        logger.debug(f'ScanCompletedEvent details: {scan_completed_event}')
        await self.scan_completed_event_producer.publish(event=scan_completed_event)
