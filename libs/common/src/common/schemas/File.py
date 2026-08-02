from pydantic import BaseModel
from pathlib import Path
from typing import Optional

class File(BaseModel):
    path: Path
    name: str
    content: Optional[str] = None