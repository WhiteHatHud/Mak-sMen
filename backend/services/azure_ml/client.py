# services/azure_ml/client.py
from __future__ import annotations
from typing import Optional, Callable, Any, Dict
import logging

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, EnvironmentCredential
from azure.ai.ml import MLClient
from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError, HttpResponseError


from .config import settings, AzureMLSettings


logger = logging.getLogger(__name__)




def _build_credential(auth) -> Any:
	"""Create a chained credential preferring Managed Identity when enabled."""
	if auth.use_managed_identity:
		try:
			return ManagedIdentityCredential()
		except Exception:
			logger.warning("ManagedIdentityCredential not available; falling back to DefaultAzureCredential")
	if auth.client_id and auth.client_secret and auth.tenant_id:
		return EnvironmentCredential()
	return DefaultAzureCredential(exclude_interactive_browser_credential=True)




def get_ml_client(cfg: AzureMLSettings = settings) -> MLClient:
	cred = _build_credential(cfg.auth)
	client = MLClient(credential=cred, subscription_id=cfg.subscription_id, resource_group=cfg.resource_group, workspace_name=cfg.workspace_name)
	return client




@retry(reraise=True,
	   stop=stop_after_attempt(5),
	   wait=wait_exponential(multiplier=0.5, min=1, max=8),
	   retry=retry_if_exception_type((ServiceRequestError, HttpResponseError)))
def _retryable(fn: Callable, *args, **kwargs):
	return fn(*args, **kwargs)




class AMLClientWrapper:
	"""Thin wrapper around azure.ai.ml.MLClient with retries and health checks."""
	def __init__(self, cfg: AzureMLSettings = settings):
		self.cfg = cfg
		self.client = get_ml_client(cfg)

	def with_retry(self, fn: Callable, *args, **kwargs):
		return _retryable(fn, *args, **kwargs)

	# -------- Registry / Model helpers --------
	def get_model(self, name: str, version: Optional[str] = None):
		if version:
			return self.with_retry(self.client.models.get, name=name, version=version)
		# latest by creation_time desc
		models = list(self.with_retry(self.client.models.list, name=name))
		if not models:
			raise ValueError(f"Model not found: {name}")
		models.sort(key=lambda m: m.version, reverse=True)
		return models[0]

	def register_model(self, path: str, name: str, version: Optional[str] = None, description: str = ""):
		from azure.ai.ml.entities import Model
		model = Model(path=path, name=name, version=version, description=description)
		return self.with_retry(self.client.models.create_or_update, model)

	# -------- Health checks --------
	def ping(self) -> Dict[str, Any]:
		try:
			ws = self.with_retry(self.client.workspaces.get, self.cfg.resource_group, self.cfg.workspace_name)
			return {"ok": True, "name": ws.name, "location": ws.location}
		except ClientAuthenticationError as e:
			logger.exception("Azure ML auth failed")
			return {"ok": False, "error": "auth_failed", "details": str(e)}
		except Exception as e:
			logger.exception("Azure ML connectivity failed")
			return {"ok": False, "error": "connectivity_failed", "details": str(e)}

