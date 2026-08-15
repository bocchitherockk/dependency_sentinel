from pydantic import BaseModel, Field

from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan

class ManifestFileUpdatePlan(BaseModel):
    manifest_file_path: str
    dependencies_updates:     list[DependencyUpdatePlan] = Field(default_factory=list)
    dev_dependencies_updates: list[DependencyUpdatePlan] = Field(default_factory=list)

    # TODO: i goota make sure that the lists could include a current_version == recommended_version
    def has_updates(self) -> bool:
        return bool(self.dependencies_updates or self.dev_dependencies_updates)
