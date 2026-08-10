from pydantic import BaseModel

from common.schemas.DependencySecurityReport import DependencySecurityReport

class DependencyUpdateContext(BaseModel):
    current_dependency_report:   DependencySecurityReport
    candidate_dependency_report: DependencySecurityReport
