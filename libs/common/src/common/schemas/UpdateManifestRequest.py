from pydantic import BaseModel
from common.schemas.File import File
from common.schemas.ManifestFileUpdateContext import ManifestFileUpdateContext

class UpdateManifestRequest(BaseModel):
    manifest_file: File
    update_context: ManifestFileUpdateContext
