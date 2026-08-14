from pydantic import BaseModel

class CreateBranchRequest(BaseModel):
    repository_name: str
    branch_name: str
