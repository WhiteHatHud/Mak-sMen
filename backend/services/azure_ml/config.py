# services/azure_ml/config.py
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field, AnyUrl, validator
import os

class AzureAuthSettings(BaseModel):
	use_managed_identity: bool = Field(default=True, description="Prefer Managed Identity on Azure")
	tenant_id: Optional[str] = Field(default=None, description="AAD tenant for service principal")
	client_id: Optional[str] = Field(default=None, description="App registration client id")
	client_secret: Optional[str] = Field(default=None, description="App registration client secret")


class ComputeSettings(BaseModel):
	cpu_instance_type: str = Field(default="Standard_DS3_v2")
	gpu_instance_type: str = Field(default="Standard_NC6s_v3")
	min_instances: int = Field(default=1, ge=0)
	max_instances: int = Field(default=3, ge=1)
	idle_time_before_scale_down: int = Field(default=600, ge=60, description="seconds")


class DeploymentSettings(BaseModel):
	model_name: str = Field(default="beth-anomaly-detector")
	model_version: Optional[str] = None
	environment_name: str = Field(default="beth-env")
	environment_docker_image: str = Field(default="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04:20230915.v1")
	environment_conda_file: Optional[str] = None
	request_timeout_ms: int = Field(default=20000, ge=1000)
	max_batch_size: int = Field(default=64, ge=1)
	traffic_split: dict = Field(default_factory=lambda: {"blue": 100})


class EndpointAuthSettings(BaseModel):
	key_enabled: bool = True
	token_auth_enabled: bool = True


class CostOptimization(BaseModel):
	spot_priority: bool = Field(default=False)
	auto_pause_minutes: int = Field(default=0, ge=0, description="For batch endpoints")


class AzureMLSettings(BaseModel):
	subscription_id: str
	resource_group: str
	workspace_name: str
	region: str = Field(default="eastus")
	auth: AzureAuthSettings = Field(default_factory=AzureAuthSettings)
	compute: ComputeSettings = Field(default_factory=ComputeSettings)
	deploy: DeploymentSettings = Field(default_factory=DeploymentSettings)
	endpoint_auth: EndpointAuthSettings = Field(default_factory=EndpointAuthSettings)
	cost: CostOptimization = Field(default_factory=CostOptimization)


@validator("subscription_id", "resource_group", "workspace_name")
def _non_empty(cls, v: str) -> str:
	if not v:
		raise ValueError("must not be empty")
	return v


# Convenience loader from env (12-factor)
def load_settings_from_env() -> AzureMLSettings:
	return AzureMLSettings(
		subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
		resource_group=os.getenv("AZURE_RESOURCE_GROUP", ""),
		workspace_name=os.getenv("AZURE_ML_WORKSPACE", ""),
		region=os.getenv("AZURE_REGION", "eastus"),
		auth=AzureAuthSettings(
			use_managed_identity=os.getenv("AZURE_USE_MI", "true").lower() == "true",
			tenant_id=os.getenv("AZURE_TENANT_ID"),
			client_id=os.getenv("AZURE_CLIENT_ID"),
			client_secret=os.getenv("AZURE_CLIENT_SECRET"),
		),
		compute=ComputeSettings(
			cpu_instance_type=os.getenv("AML_CPU_SKU", "Standard_DS3_v2"),
			gpu_instance_type=os.getenv("AML_GPU_SKU", "Standard_NC6s_v3"),
			min_instances=int(os.getenv("AML_MIN_INSTANCES", "1")),
			max_instances=int(os.getenv("AML_MAX_INSTANCES", "3")),
			idle_time_before_scale_down=int(os.getenv("AML_IDLE_SECONDS", "600")),
		),
		deploy=DeploymentSettings(
			model_name=os.getenv("AML_MODEL_NAME", "beth-anomaly-detector"),
			model_version=os.getenv("AML_MODEL_VERSION"),
			environment_name=os.getenv("AML_ENV_NAME", "beth-env"),
			environment_docker_image=os.getenv("AML_ENV_IMAGE", "mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04:20230915.v1"),
			environment_conda_file=os.getenv("AML_ENV_CONDA"),
			request_timeout_ms=int(os.getenv("AML_REQUEST_TIMEOUT_MS", "20000")),
			max_batch_size=int(os.getenv("AML_MAX_BATCH", "64")),
		),
		endpoint_auth=EndpointAuthSettings(
			key_enabled=os.getenv("AML_ENDPOINT_KEY_ENABLED", "true").lower() == "true",
			token_auth_enabled=os.getenv("AML_ENDPOINT_TOKEN_ENABLED", "true").lower() == "true",
		),
		cost=CostOptimization(
			spot_priority=os.getenv("AML_SPOT_PRIORITY", "false").lower() == "true",
			auto_pause_minutes=int(os.getenv("AML_AUTO_PAUSE_MIN", "0")),
		)
	)

# Alias for imports used elsewhere
settings = load_settings_from_env()