
from common.schemas.File import File
from common.schemas.Dependency import Dependency

class ManifestFile(File):
    dependencies:     list[Dependency]
    dev_dependencies: list[Dependency]
