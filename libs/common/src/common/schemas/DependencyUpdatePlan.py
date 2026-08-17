from pydantic import BaseModel

class DependencyUpdatePlan(BaseModel):
    name: str
    current_version: str
    recommended_version: str
    reasoning: str
