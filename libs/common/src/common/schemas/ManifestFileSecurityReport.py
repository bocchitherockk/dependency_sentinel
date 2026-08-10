from pydantic import Field

from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencySecurityReport import DependencySecurityReport

class ManifestFileSecurityReport(ManifestFile):
    dependencies_security_reports:     list[DependencySecurityReport] = Field(default_factory=list)
    dev_dependencies_security_reports: list[DependencySecurityReport] = Field(default_factory=list)
