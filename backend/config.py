"""
Application configuration settings.
Uses environment variables with fallback defaults.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Anomaly Detection Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_VERSION: str = "v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/beth_anomaly_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Azure Storage
    AZURE_BLOB_CONNECTION_STRING: Optional[str] = None
    AZURE_BLOB_ACCOUNT_URL: Optional[str] = None
    AZURE_BLOB_ACCOUNT_NAME: Optional[str] = None
    AZURE_BLOB_ACCOUNT_KEY: Optional[str] = None
    AZURE_BLOB_CONTAINER: str = "beth-data"
    
    # Azure ML
    AZURE_ML_SUBSCRIPTION_ID: Optional[str] = None
    AZURE_ML_RESOURCE_GROUP: Optional[str] = None
    AZURE_ML_WORKSPACE_NAME: Optional[str] = None
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    
    # JWT Authentication
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File Storage
    FILE_STORAGE_DIR: str = "./storage"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_FILE_TYPES: list = [".csv", ".json", ".parquet", ".xlsx", ".pdf"]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Monitoring
    PROMETHEUS_PORT: int = 8001
    LOG_LEVEL: str = "INFO"
    
    # Email (for reports)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_TLS: bool = True
    SMTP_FROM: str = "noreply@anomaly-platform.com"
    
    # Analysis
    ANALYSIS_CHUNK_ROWS: int = 200000
    ANALYSIS_TOP_N: int = 100
    ANALYSIS_PROB_THRESHOLD: float = 0.98
    
    # Webhooks
    WEBHOOK_CB_WINDOW: int = 300  # seconds
    WEBHOOK_CB_THRESHOLD: int = 5  # failures
    WEBHOOK_CB_COOLDOWN: int = 300  # seconds
    WEBHOOK_DLQ_KEY: str = "webhooks:dlq"
    
    # Reports
    REPORT_DIR: str = "./reports"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()