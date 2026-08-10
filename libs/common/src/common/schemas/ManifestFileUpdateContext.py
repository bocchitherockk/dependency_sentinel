from pydantic import BaseModel

from common.schemas.ManifestFileSecurityReport import ManifestFileSecurityReport

class ManifestFileUpdateContext(BaseModel):
    current_manifest_file_report: ManifestFileSecurityReport
    candidate_manifest_file_report: ManifestFileSecurityReport
