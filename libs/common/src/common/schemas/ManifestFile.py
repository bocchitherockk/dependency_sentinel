from pydantic import BaseModel, Field

from common.schemas.Dependency import Dependency

class ManifestFile(BaseModel):
    # TODO: change to Path type instead of str.
    path: str
    dependencies:     list[Dependency] = Field(default_factory=list)
    dev_dependencies: list[Dependency] = Field(default_factory=list)
