from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

from common.schemas.ManifestFile import ManifestFile

class RepositoryScannedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_REPOSITORY_SCANNED
    repository_name: str
    detected_manifest_files: list[ManifestFile]