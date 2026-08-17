from events.schemas.BaseEvent import BaseEvent
from events.config import KafkaConfig
from common.schemas.File import File

class ManifestFilesEditedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_MANIFEST_FILES_EDITED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
    updated_manifest_files: list[File]
