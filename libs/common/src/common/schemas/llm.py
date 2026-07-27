from pydantic import BaseModel, Field


class DetectManifestsRequest(BaseModel):
    repository_files: list[str] = Field(
        min_length=1,
    )


class ManifestCandidate(BaseModel):
    path: str
    ecosystem: str = "unknown"
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    reason: str = ""


class DetectManifestsResponse(BaseModel):
    manifest_files: list[ManifestCandidate] = Field(
        default_factory=list,
    )


class ParseManifestRequest(BaseModel):
    path: str
    content: str


class DependencyResult(BaseModel):
    name: str
    version: str | None = None
    scope: str | None = None
    direct: bool | None = None


class ParseManifestResponse(BaseModel):
    path: str
    ecosystem: str = "unknown"

    dependencies: list[DependencyResult] = Field(
        default_factory=list,
    )

    warnings: list[str] = Field(
        default_factory=list,
    )