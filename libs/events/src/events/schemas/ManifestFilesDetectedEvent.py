from common.schemas.File import File

from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class ManifestFilesDetectedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_MANIFEST_FILES_DETECTED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
    detected_manifest_files: list[File]
