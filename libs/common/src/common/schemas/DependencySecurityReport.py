
from common.schemas.Dependency import Dependency
from common.schemas.VulnerabilityItem import VulnerabilityItem

class DependencySecurityReport(Dependency):
    vulnerabilities: list[VulnerabilityItem]
