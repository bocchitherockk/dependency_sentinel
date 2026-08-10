from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from pathlib import Path

from common.schemas.File import File

class Directory(BaseModel):
    path: Path
    name: str
    children: list[Directory | File] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_unique_children(self):
        names = [child.name for child in self.children]

        if len(names) != len(set(names)):
            raise ValueError('Directory contains duplicate child names')

        return self