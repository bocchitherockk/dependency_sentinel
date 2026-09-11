from pydantic import BaseModel

class DependencyUpdatePlan(BaseModel):
    name: str
    current_version: str
    recommended_version: str
    reasoning: str
    
    def is_update(self) -> bool:
        return self.current_version != self.recommended_version
