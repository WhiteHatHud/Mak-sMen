# services/azure_ml/endpoints.py
from __future__ import annotations
from typing import Optional, Dict, Any
import logging

from azure.ai.ml.entities import (
    ManagedOnlineEndpoint,
    ManagedOnlineDeployment,
    Model,
    Environment,
    CodeConfiguration,
    BatchEndpoint,
    BatchDeployment,
)
from azure.core.exceptions import HttpResponseError

from .client import AMLClientWrapper
from .config import settings


logger = logging.getLogger(__name__)

class EndpointManager:
	def __init__(self, client: Optional[AMLClientWrapper] = None):
		self.client = client or AMLClientWrapper(settings)

	# ---------------- Real-time endpoints ----------------
	def deploy_realtime(
		self,
		endpoint_name: str,
		model: Model,
		code_path: str,
		scoring_script: str,
		instance_type: Optional[str] = None,
		instance_count: Optional[int] = None,
		env_name: Optional[str] = None,
		conda_file: Optional[str] = None,
		docker_image: Optional[str] = None,
		traffic_weight: int = 100,
		deployment_name: str = "blue",
		enable_app_insights: bool = True,
		token_auth: Optional[bool] = None,
		key_auth: Optional[bool] = None,
	) -> Dict[str, Any]:
		cfg = settings
		instance_type = instance_type or cfg.compute.cpu_instance_type
		instance_count = instance_count or cfg.compute.min_instances
		env_name = env_name or cfg.deploy.environment_name
		docker_image = docker_image or cfg.deploy.environment_docker_image
		token_auth = cfg.endpoint_auth.token_auth_enabled if token_auth is None else token_auth
		key_auth = cfg.endpoint_auth.key_enabled if key_auth is None else key_auth

		env = Environment(name=env_name, image=docker_image, conda_file=conda_file)
		code = CodeConfiguration(code=code_path, scoring_script=scoring_script)

		ep = ManagedOnlineEndpoint(
			name=endpoint_name,
			auth_mode=("aad_token" if token_auth else "key") if key_auth is False else ("key" if key_auth else "aad_token"),
			traffic={deployment_name: traffic_weight},
			tags={"app": "beth", "type": "realtime"},
		)
		dep = ManagedOnlineDeployment(
			name=deployment_name,
			endpoint_name=endpoint_name,
			model=model,
			environment=env,
			code_configuration=code,
			instance_type=instance_type,
			instance_count=instance_count,
			request_settings={"request_timeout_ms": cfg.deploy.request_timeout_ms},
		)
		logger.info("Creating/updating realtime endpoint", extra={"endpoint": endpoint_name, "deployment": deployment_name})
		self.client.with_retry(self.client.client.begin_create_or_update, ep).wait()
		self.client.with_retry(self.client.client.begin_create_or_update, dep).wait()
		return {"endpoint": endpoint_name, "deployment": deployment_name}

	def update_traffic(self, endpoint_name: str, splits: Dict[str, int]) -> Dict[str, Any]:
		ep = self.client.client.online_endpoints.get(endpoint_name)
		ep.traffic = splits
		self.client.with_retry(self.client.client.begin_create_or_update, ep).wait()
		return {"endpoint": endpoint_name, "traffic": splits}

	def scale_deployment(self, endpoint_name: str, deployment_name: str, instance_count: int) -> Dict[str, Any]:
		dep = self.client.client.online_deployments.get(endpoint_name, deployment_name)
		dep.instance_count = instance_count
		self.client.with_retry(self.client.client.begin_create_or_update, dep).wait()
		return {"endpoint": endpoint_name, "deployment": deployment_name, "instance_count": instance_count}

	# ---------------- Batch endpoints ----------------
	def deploy_batch(
		self,
		endpoint_name: str,
		model: Model,
		code_path: str,
		scoring_script: str,
		compute_name: Optional[str] = None,
		mini_batch_size: int = 1,
		max_concurrency_per_instance: int = 1,
		deployment_name: str = "batch-blue",
	) -> Dict[str, Any]:
		compute_name = compute_name or f"cpu-{settings.compute.cpu_instance_type}".replace("_", "-")
		code = CodeConfiguration(code=code_path, scoring_script=scoring_script)
		be = BatchEndpoint(name=endpoint_name, tags={"app": "beth", "type": "batch"})
		bd = BatchDeployment(
			name=deployment_name,
			endpoint_name=endpoint_name,
			model=model,
			code_configuration=code,
			compute=compute_name,
			settings={
				"mini_batch_size": mini_batch_size,
				"max_concurrency_per_instance": max_concurrency_per_instance,
			},
		)
		logger.info("Creating/updating batch endpoint", extra={"endpoint": endpoint_name})
		self.client.with_retry(self.client.client.batch_endpoints.begin_create_or_update, be).result()
		self.client.with_retry(self.client.client.batch_deployments.begin_create_or_update, bd).result()
		return {"endpoint": endpoint_name, "deployment": deployment_name}

	# ---------------- Versioning helpers ----------------
	def get_latest_model(self, name: str):
		return self.client.get_model(name)

	def get_model_version(self, name: str, version: str):
		return self.client.get_model(name, version)

	# ---------------- Monitoring stubs ----------------
	def enable_app_insights(self, endpoint_name: str, enabled: bool = True):
		ep = self.client.client.online_endpoints.get(endpoint_name)
		ep.mirror_traffic_to = None  # explicit clear of mirror if any
		ep.tags = {**(ep.tags or {}), "app_insights": str(enabled).lower()}
		self.client.with_retry(self.client.client.begin_create_or_update, ep).wait()
		return {"endpoint": endpoint_name, "app_insights": enabled}

	# ---------------- Request/response logging ----------------
	def score(self, endpoint_name: str, request: Dict[str, Any], deployment: Optional[str] = None) -> Dict[str, Any]:
		try:
			if deployment:
				resp = self.client.client.online_endpoints.invoke(
					endpoint_name=endpoint_name,
					request_body=request,
					deployment_name=deployment,
				)
			else:
				resp = self.client.client.online_endpoints.invoke(
					endpoint_name=endpoint_name,
					request_body=request,
				)
			logger.info("AML score request", extra={"endpoint": endpoint_name, "deployment": deployment})
			return resp
		except HttpResponseError as e:
			logger.exception("AML scoring failed", extra={"endpoint": endpoint_name})
			raise

