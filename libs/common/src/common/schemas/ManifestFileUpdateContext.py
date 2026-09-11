
from common.schemas.ManifestFile import ManifestFile
from common.schemas.DependencyUpdateContext import DependencyUpdateContext

class ManifestFileUpdateContext(ManifestFile):
    dependencies_update_context:     list[DependencyUpdateContext]
    dev_dependencies_update_context: list[DependencyUpdateContext]
