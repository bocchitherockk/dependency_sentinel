from pydantic import BaseModel

from common.schemas.DependencySecurityReport import DependencySecurityReport

class DependencyUpdateContext(BaseModel):
    current_version_dependency_report: DependencySecurityReport
    latest_compatible_version_dependency_report: DependencySecurityReport | None
    latest_version_dependency_report: DependencySecurityReport | None
