from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class ScanStartedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_SCAN_STARTED
    repository_url: str
