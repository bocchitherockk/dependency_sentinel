from pydantic import BaseModel, Field

from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan

class ManifestFileUpdatePlan(BaseModel):
    manifest_file_path: str
    dependencies_updates:     list[DependencyUpdatePlan] = Field(default_factory=list)
    dev_dependencies_updates: list[DependencyUpdatePlan] = Field(default_factory=list)

    def remove_unnecessary_update_elements(self) -> None:
        self.dependencies_updates = [
            dependency_update_plan
            for dependency_update_plan in self.dependencies_updates
            if dependency_update_plan.current_version != dependency_update_plan.recommended_version
        ]
        self.dev_dependencies_updates = [
            dev_dependency_update_plan
            for dev_dependency_update_plan in self.dev_dependencies_updates
            if dev_dependency_update_plan.current_version != dev_dependency_update_plan.recommended_version
        ]

    def has_updates(self) -> bool:
        return bool(self.dependencies_updates or self.dev_dependencies_updates)
