from pydantic import BaseModel

from common.schemas.DependencyUpdateContext import DependencyUpdateContext

class ManifestFileUpdateContext(BaseModel):
    manifest_file_path: str
    dependencies_update_context:     list[DependencyUpdateContext]
    dev_dependencies_update_context: list[DependencyUpdateContext]
