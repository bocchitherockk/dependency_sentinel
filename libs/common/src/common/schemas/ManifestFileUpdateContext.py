from pydantic import BaseModel, Field

from common.schemas.DependencyUpdateContext import DependencyUpdateContext

class ManifestFileUpdateContext(BaseModel):
    dependencies_update_context:     list[DependencyUpdateContext] = Field(default_factory=list)
    dev_dependencies_update_context: list[DependencyUpdateContext] = Field(default_factory=list)
