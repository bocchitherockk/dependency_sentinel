from pydantic import BaseModel

class DependencyUpdatePlan(BaseModel):
    name: str
    current_version: str | None
    recommended_version: str | None
    reasoning: str
