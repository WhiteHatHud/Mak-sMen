from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, constr
from api.middleware.auth import get_current_user
from services.storage.file_handler import ProjectNotFoundError
from models.project import Project
from utils.logger import logger
from utils.helpers import to_pagination
from utils.metrics import record_api_latency


router = APIRouter(prefix="/api/projects", tags=["projects"])


# -----------------------------
# Schemas & Response Envelope
# -----------------------------
class ApiError(BaseModel):
	code: constr(strip_whitespace=True) = Field(..., description="Application-specific error code")
	message: str
	details: Optional[dict] = None


class ApiResponse(BaseModel):
	success: bool = True
	data: Optional[dict] = None
	error: Optional[ApiError] = None


class ProjectCreate(BaseModel):
	name: constr(min_length=1, max_length=200)
	description: Optional[constr(max_length=1000)] = None


class ProjectUpdate(BaseModel):
	name: Optional[constr(min_length=1, max_length=200)] = None
	description: Optional[constr(max_length=1000)] = None


class ProjectOut(BaseModel):
	id: int
	name: str
	description: Optional[str]
	created_at: str
	updated_at: str
	deleted: bool


class PaginatedProjects(BaseModel):
	items: List[ProjectOut]
	total: int
	page: int
	size: int


# -----------------------------
# Helpers
# -----------------------------


def ok(data: dict) -> ApiResponse:
	return ApiResponse(success=True, data=data)


# -----------------------------
# Routes
# -----------------------------
@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
@record_api_latency
async def create_project(payload: ProjectCreate, user=Depends(get_current_user)):
	"""Create a new project."""
	try:
		project = await Project.create(name=payload.name, description=payload.description, owner_id=user.id)
		return ok({"project": ProjectOut(**project.to_dict())})
	except Exception as e:
		logger.exception("PROJECT_CREATE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to create project")




@router.get("", response_model=ApiResponse)
@record_api_latency
async def list_projects(
	page: int = Query(1, ge=1),
	size: int = Query(20, ge=1, le=100),
	user=Depends(get_current_user),
):
	"""List projects with pagination."""
	try:
		items, total = await Project.list_paginated(owner_id=user.id, page=page, size=size)
		data = PaginatedProjects(
			items=[ProjectOut(**p.to_dict()) for p in items], total=total, page=page, size=size
		).dict()
		return ok(data)
	except Exception:
		logger.exception("PROJECT_LIST_FAILED")
		raise HTTPException(status_code=500, detail="Failed to list projects")

@router.get("/{project_id}", response_model=ApiResponse)
@record_api_latency
async def get_project(project_id: int, user=Depends(get_current_user)):
	try:
		project = await Project.get(project_id, owner_id=user.id)
		if not project:
			raise HTTPException(status_code=404, detail="Project not found")
		return ok({"project": ProjectOut(**project.to_dict())})
	except HTTPException:
		raise
	except Exception:
		logger.exception("PROJECT_GET_FAILED")
		raise HTTPException(status_code=500, detail="Failed to get project")


@router.put("/{project_id}", response_model=ApiResponse)
@record_api_latency
async def update_project(project_id: int, payload: ProjectUpdate, user=Depends(get_current_user)):
	try:
		project = await Project.get(project_id, owner_id=user.id)
		if not project:
			raise HTTPException(status_code=404, detail="Project not found")
		updated = await Project.update(project_id, **payload.dict(exclude_unset=True))
		return ok({"project": ProjectOut(**updated.to_dict())})
	except HTTPException:
		raise
	except Exception:
		logger.exception("PROJECT_UPDATE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to update project")


@router.delete("/{project_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
@record_api_latency
async def delete_project(project_id: int, user=Depends(get_current_user)):
	try:
		project = await Project.get(project_id, owner_id=user.id)
		if not project:
			raise HTTPException(status_code=404, detail="Project not found")
		await Project.soft_delete(project_id)
		return ok({"deleted": True, "project_id": project_id})
	except HTTPException:
		raise
	except Exception:
		logger.exception("PROJECT_DELETE_FAILED")
		raise HTTPException(status_code=500, detail="Failed to delete project")