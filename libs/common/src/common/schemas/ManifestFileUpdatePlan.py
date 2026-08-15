from pydantic import BaseModel, Field

from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan

class ManifestFileUpdatePlan(BaseModel):
    dependency_updates:     list[DependencyUpdatePlan] = Field(default_factory=list)
    dev_dependency_updates: list[DependencyUpdatePlan] = Field(default_factory=list)
