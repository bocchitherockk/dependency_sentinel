from __future__ import annotations

from pydantic import BaseModel, Field
from pathlib import Path

from common.schemas.File import File

class Directory(BaseModel):
    path: Path
    name: str
    children: list[Directory | File] = Field(default_factory=list)