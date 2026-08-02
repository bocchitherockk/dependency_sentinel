from pydantic import BaseModel, Field

from common.schemas.Dependency import Dependency

class ManifestFile(BaseModel):
    """Un fichier manifest détecté dans un repo"""
    path: str                                    
    dependencies: list[Dependency] = Field(default_factory=list) 
    dev_dependencies: list[Dependency] = Field(default_factory=list) 