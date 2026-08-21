from logging import Logger

from pydantic import BaseModel, Field

from common.logging.global_logger import get_global_logger
from common.schemas.DependencyUpdatePlan import DependencyUpdatePlan

logger: Logger = get_global_logger(__name__)

class ManifestFileUpdatePlan(BaseModel):
    manifest_file_path: str
    dependencies_updates:     list[DependencyUpdatePlan] = Field(default_factory=list)
    dev_dependencies_updates: list[DependencyUpdatePlan] = Field(default_factory=list)

    def remove_unnecessary_update_elements(self) -> None:
        new_dependencies_updates: list[DependencyUpdatePlan] = []
        for dependency_update_plan in self.dependencies_updates:
            if dependency_update_plan.current_version != dependency_update_plan.recommended_version:
                new_dependencies_updates.append(dependency_update_plan)
            else:
                logger.debug(f"Removing unnecessary dependency update for '{dependency_update_plan.dependency_name}' in manifest file '{self.manifest_file_path}' as current version '{dependency_update_plan.current_version}' is the same as recommended version '{dependency_update_plan.recommended_version}'.")

        new_dev_dependencies_updates: list[DependencyUpdatePlan] = []
        for dev_dependency_update_plan in self.dev_dependencies_updates:
            if dev_dependency_update_plan.current_version != dev_dependency_update_plan.recommended_version:
                new_dev_dependencies_updates.append(dev_dependency_update_plan)
            else:
                logger.debug(f"Removing unnecessary dev dependency update for '{dev_dependency_update_plan.dependency_name}' in manifest file '{self.manifest_file_path}' as current version '{dev_dependency_update_plan.current_version}' is the same as recommended version '{dev_dependency_update_plan.recommended_version}'.")

        if len(new_dependencies_updates) != len(self.dependencies_updates) or len(new_dev_dependencies_updates) != len(self.dev_dependencies_updates):
            logger.info(f"Removed unnecessary updates from ManifestFileUpdatePlan for manifest file '{self.manifest_file_path}'.")
            logger.debug(f'Updated ManifestFileUpdatePlan details: {self}')
        else:
            logger.info(f"No unnecessary updates found in ManifestFileUpdatePlan for manifest file '{self.manifest_file_path}'.")

        self.dependencies_updates = new_dependencies_updates
        self.dev_dependencies_updates = new_dev_dependencies_updates

    def has_updates(self) -> bool:
        result: bool = bool(self.dependencies_updates or self.dev_dependencies_updates)
        if result:
            logger.info(f"ManifestFileUpdatePlan for manifest file '{self.manifest_file_path}' has updates.")
        else:
            logger.info(f"ManifestFileUpdatePlan for manifest file '{self.manifest_file_path}' has no updates.")

        return result
