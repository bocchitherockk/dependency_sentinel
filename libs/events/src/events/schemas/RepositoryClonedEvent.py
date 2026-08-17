from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent

class RepositoryClonedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_REPOSITORY_CLONED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
