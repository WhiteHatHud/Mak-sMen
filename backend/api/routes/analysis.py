from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.middleware.auth import get_current_user
from workers.analysis_worker import start_analysis, cancel_analysis
from models.analysis_result import AnalysisStatus
from utils.logger import logger


router = APIRouter(prefix="/api", tags=["analysis"])


class ApiResponse(BaseModel):
	success: bool = True
	data: Optional[dict] = None
	error: Optional[dict] = None


class AnalysisRunRequest(BaseModel):
    project_id: int = Field(..., ge=1)
    file_ids: List[int] = Field(..., min_length=1, description="List of file IDs to analyze")
    ai_endpoint: str = Field(..., description="Azure ML endpoint name or URL")
    enable_llm_explain: bool = False


class AnalysisRunResponse(BaseModel):
	analysis_id: str


class AnalysisStatusOut(BaseModel):
	id: str
	status: str
	progress: Optional[float] = None
	started_at: Optional[str] = None
	finished_at: Optional[str] = None




def ok(data: dict) -> ApiResponse:
	return ApiResponse(success=True, data=data)




@router.post("/analysis/run", response_model=ApiResponse)
async def run_analysis(body: AnalysisRunRequest, user=Depends(get_current_user)):
	try:
		task = start_analysis.delay(user_id=user.id, **body.dict())
		return ok(AnalysisRunResponse(analysis_id=task.id).dict())
	except Exception:
		logger.exception("ANALYSIS_RUN_FAILED")
		raise HTTPException(status_code=500, detail="Failed to start analysis")




@router.get("/analysis/{analysis_id}/status", response_model=ApiResponse)
async def analysis_status(analysis_id: str, user=Depends(get_current_user)):
	try:
		status_info = AnalysisStatus.get(analysis_id=analysis_id, user_id=user.id)
		if not status_info:
			raise HTTPException(status_code=404, detail="Analysis not found")
		return ok({"status": AnalysisStatusOut(**status_info).dict()})
	except HTTPException:
		raise
	except Exception:
		logger.exception("ANALYSIS_STATUS_FAILED")
		raise HTTPException(status_code=500, detail="Failed to get status")



@router.get("/analysis/{analysis_id}/results", response_model=ApiResponse)
async def analysis_results(analysis_id: str, user=Depends(get_current_user)):
	try:
		results = AnalysisStatus.get_results(analysis_id=analysis_id, user_id=user.id)
		if results is None:
			raise HTTPException(status_code=404, detail="Results not found")
		return ok({"results": results})
	except HTTPException:
		raise
	except Exception:
		logger.exception("ANALYSIS_RESULTS_FAILED")
		raise HTTPException(status_code=500, detail="Failed to list analyses")

@router.post("/analysis/{analysis_id}/cancel", response_model=ApiResponse)
async def cancel(analysis_id: str, user=Depends(get_current_user)):
	try:
		cancelled = cancel_analysis(analysis_id)
		return ok({"cancelled": bool(cancelled), "analysis_id": analysis_id})
	except Exception:
		logger.exception("ANALYSIS_CANCEL_FAILED")
		raise HTTPException(status_code=500, detail="Failed to cancel analysis")



@router.get("/projects/{project_id}/analyses", response_model=ApiResponse)
async def list_analyses(project_id: int, user=Depends(get_current_user)):
	try:
		items = AnalysisStatus.list_by_project(project_id=project_id, user_id=user.id)
		return ok({"analyses": items})
	except Exception:
		logger.exception("ANALYSIS_LIST_FAILED")
		raise HTTPException(status_code=500, detail="Failed to list analyses")