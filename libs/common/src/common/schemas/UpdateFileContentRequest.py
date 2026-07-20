from pydantic import BaseModel

class UpdateFileContentRequest(BaseModel):
    new_content: str
