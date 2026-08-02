from pydantic import BaseModel
from typing import Optional

class StartScanRequest(BaseModel):
    repository_url: str
    access_key: Optional[str] = None
    # TODO: Add support for access keys for private repositories
