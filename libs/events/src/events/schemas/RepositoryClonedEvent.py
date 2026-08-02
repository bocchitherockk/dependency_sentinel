from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class RepositoryClonedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_REPOSITORY_CLONED
    repository_name: str
