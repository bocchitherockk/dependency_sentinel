from pydantic import BaseModel

class CloneRepositoryRequest(BaseModel):
    repository_url: str
