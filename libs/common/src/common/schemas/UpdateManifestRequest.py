from pydantic import BaseModel
from common.schemas.File import File
from common.schemas.ManifestFileUpdatePlan import ManifestFileUpdatePlan

class UpdateManifestRequest(BaseModel):
    manifest_file: File
    update_plan: ManifestFileUpdatePlan
