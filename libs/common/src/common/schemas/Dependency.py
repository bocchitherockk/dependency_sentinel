from pydantic import BaseModel
from common.schemas.Registry import Registry

class Dependency(BaseModel):
    name: str
    version: str
    registry: Registry