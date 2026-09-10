from common.schemas.ManifestFile import ManifestFile
from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class DependenciesExtractedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_DEPENDENCIES_EXTRACTED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
    manifest_files: list[ManifestFile]
