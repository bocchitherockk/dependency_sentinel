from common.schemas.File import File

from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class ManifestFilesContentRetrievedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_MANIFEST_FILES_CONTENT_RETRIEVED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
    manifest_files: list[File]
