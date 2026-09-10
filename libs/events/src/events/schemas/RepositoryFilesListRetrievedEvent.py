from common.schemas.File import File

from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class RepositoryFilesListRetrievedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_REPOSITORY_FILES_LIST_RETRIEVED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
    retrieved_repository_files_list: list[File]
