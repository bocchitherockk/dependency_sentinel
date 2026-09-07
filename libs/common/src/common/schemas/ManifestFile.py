from pydantic import BaseModel

from common.schemas.Dependency import Dependency

class ManifestFile(BaseModel):
    # TODO: change to Path type instead of str.
    path: str
    dependencies:     list[Dependency]
    dev_dependencies: list[Dependency]
