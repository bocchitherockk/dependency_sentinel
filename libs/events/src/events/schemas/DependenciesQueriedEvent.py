from events.config import KafkaConfig
from events.schemas.BaseEvent import BaseEvent
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext

class DependenciesQueriedEvent(BaseEvent):
    event_type: str = KafkaConfig.TOPIC_DEPENDENCIES_QUERIED
    repository_url: str
    repository_name: str
    repository_owner_name: str
    default_branch: str
    manifest_files_update_context: list[ManifestFileUpdateContext]
