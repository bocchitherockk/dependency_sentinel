from pydantic import BaseModel

class RepositoryScanSchedule(BaseModel):
    repository_url: str
    interval_seconds: int
