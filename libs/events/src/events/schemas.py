from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# --- 1. STRUCTURE D'UN MANIFEST ---
class Manifest(BaseModel):
    """Un fichier manifest détecté dans un repo"""
    path: str                                    
    programming_language: str                    
    dependency_manager: Optional[str] = None     
    reasoning: str                              
    dependencies: Optional[List[dict[str, str]]] = Field(default_factory=list) 