from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

from common.schemas.File import File

class ScanCompletedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_SCAN_COMPLETED
    repository_name: str
    repository_owner_name: str
