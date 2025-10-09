"""Pydantic request/response schemas with constraints and examples (Pydantic v2)."""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, HttpUrl, conint, constr, field_validator

# ---------- Shared envelope ----------
class ApiError(BaseModel):
    code: constr(min_length=1) = Field(..., examples=["VALIDATION_ERROR"])
    message: str = Field(..., examples=["Invalid input"])
    details: Optional[Dict[str, Any]] = None

class ApiResponse(BaseModel):
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    error: Optional[ApiError] = None

# ---------- Projects ----------
class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "BETH Fraud Triage", "description": "Detect anomalies in BETH dataset uploads"}
    })
    name: constr(min_length=1, max_length=200)
    description: Optional[constr(max_length=1000)] = None

    @field_validator("name")
    @classmethod
    def _no_forbidden_names(cls, v: str) -> str:
        if v.strip().lower() in {"test", "null", "undefined"}:
            raise ValueError("Project name is reserved")
        return v.strip()

class ProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "BETH Triage v2", "description": "Refined scope"}
    })
    name: Optional[constr(min_length=1, max_length=200)] = None
    description: Optional[constr(max_length=1000)] = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str
    deleted: bool = False

# ---------- Files ----------
class FileUploadRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"project_id": 42, "filenames": ["data.csv", "evidence.parquet"]}
    })
    project_id: conint(ge=1)
    filenames: List[str] = Field(..., min_length=1)

class FileResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    content_type: Optional[str]
    size_bytes: int
    created_at: str

# ---------- Analysis ----------
class AnalysisRunRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "project_id": 42,
            "file_ids": [1, 2, 3],
            "ai_endpoint": "beth-detector-prod",
            "enable_llm_explain": True
        }
    })
    project_id: conint(ge=1)
    file_ids: List[conint(ge=1)] = Field(..., min_length=1)
    ai_endpoint: constr(min_length=1, max_length=200)
    enable_llm_explain: bool = False

    @field_validator("file_ids")
    @classmethod
    def _unique_file_ids(cls, v: List[int]) -> List[int]:
        if len(set(v)) != len(v):
            raise ValueError("Duplicate file IDs are not allowed")
        return v

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    progress: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    started_at: Optional[str]
    finished_at: Optional[str]

# ---------- Reports ----------
class ReportGenerateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"analysis_id": "9d1c...", "format": "pdf"}
    })
    analysis_id: constr(min_length=1)
    format: constr(pattern=r"^(pdf|html|json)$")

class ReportResponse(BaseModel):
    id: int
    analysis_id: str
    project_id: int
    path: Optional[str]
    format: str
    status: str
    created_at: str

# ---------- Webhooks ----------
class WebhookRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "url": "https://hooks.example.com/anomalies",
            "secret": "hmac-secret",
            "event": "analysis.completed",
            "active": True
        }
    })
    url: HttpUrl
    secret: Optional[str] = Field(default=None, max_length=256)
    event: constr(min_length=3, max_length=64)
    active: bool = True

class WebhookResponse(BaseModel):
    id: int
    url: HttpUrl
    event: str
    active: bool
    created_at: str
