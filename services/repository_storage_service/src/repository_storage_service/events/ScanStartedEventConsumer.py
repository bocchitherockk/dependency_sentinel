from logging import Logger
from pathlib import Path
from urllib.parse import urlparse

from git import Repo

from common.logging.global_logger import get_global_logger
from events.consumer import EventConsumer
from events.config import KafkaConfig
from events.schemas.ScanStartedEvent import ScanStartedEvent
from events.schemas.RepositoryClonedEvent import RepositoryClonedEvent

from repository_storage_service.events.RepositoryClonedEventProducer import RepositoryClonedEventProducer
from repository_storage_service.config import REPOSITORIES_PATH

logger: Logger = get_global_logger(__name__)

def get_repository_name_and_owner_name(repository_url: str) -> tuple[str, str]:
    if repository_url.startswith('git@'):
        # git@github.com:owner/repo.git
        path = repository_url.split(':', 1)[1]
    else:
        # https://github.com/owner/repo.git
        path = urlparse(repository_url).path.lstrip('/')

    repository_owner_name, repository_name = path.removesuffix('.git').split('/', 1)
    return repository_owner_name, repository_name

def clone_repository(repository_url: str, destination: Path) -> str:
    default_branch: str = 'main'  # Default to 'main' if we can't determine the default branch
    if not destination.exists():
        repo: Repo = Repo.clone_from(repository_url, destination)
        default_branch = repo.active_branch.name
        logger.info(f"Repository cloned successfully from '{repository_url}' to '{destination}'. Default branch: {default_branch}")
    else:
        # Pull the latest changes if the repository already exists
        # Hard reset and clean to ensure the local repository state exactly matches the remote state
        repo: Repo = Repo(destination)
        origin = repo.remotes.origin
        origin.fetch()
        default_branch = repo.git.symbolic_ref('refs/remotes/origin/HEAD').split('/')[-1]
        repo.git.reset('--hard', f'origin/{default_branch}')
        repo.git.clean('-fd')
        logger.info(f"Repository at '{destination}' updated successfully. Default branch: {default_branch}")
        
    return default_branch  # Return the default branch name for further use (e.g., creating a pull request)

class ScanStartedEventConsumer(EventConsumer):
    def __init__(self, repository_cloned_event_producer: RepositoryClonedEventProducer):
        self.repository_cloned_event_producer: RepositoryClonedEventProducer = repository_cloned_event_producer
        super().__init__(
            topic=KafkaConfig.TOPIC_SCAN_STARTED,
            group_id=KafkaConfig.CONSUMER_GROUP_REPOSITORY_STORAGE_SERVICE,
            callback=self.handle,
        )

    async def handle(self, key: str, value: dict, msg):
        scan_started_event: ScanStartedEvent = ScanStartedEvent(**value)
        logger.info(f'Received ScanStartedEvent for repository: {scan_started_event.repository_url}')
        logger.debug(f'ScanStartedEvent details: {scan_started_event}')
        repository_url: str = scan_started_event.repository_url
        repository_owner_name, repository_name = get_repository_name_and_owner_name(repository_url)
        destination: Path = REPOSITORIES_PATH / repository_name

        default_branch: str = clone_repository(repository_url, destination)

        repository_cloned_event: RepositoryClonedEvent = RepositoryClonedEvent(
            key=repository_name,
            repository_url=repository_url,
            repository_name=repository_name,
            repository_owner_name=repository_owner_name,
            default_branch=default_branch,
        )
        logger.info(f'Publishing RepositoryClonedEvent for repository: {repository_name}')
        logger.debug(f'RepositoryClonedEvent details: {repository_cloned_event}')
        await self.repository_cloned_event_producer.publish(event=repository_cloned_event)
