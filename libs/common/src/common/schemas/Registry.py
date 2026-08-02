from pydantic import BaseModel

class Registry(BaseModel):
    name: str
    url: str