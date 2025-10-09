"""
Main application entry point for the Anomaly Detection Platform.
Initializes FastAPI app with all routes, middleware, and configurations.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
from typing import Dict, Any

# Import configurations
from config import settings
from database.connection import engine, Base

# Import routers
from api.routes import projects, files, analysis, reports, webhooks

# Import middleware
from api.middleware.auth import auth_middleware
from api.middleware.rate_limiter import RateLimitMiddleware
from api.middleware.cors import configure_cors

# Import services
from services.azure_ml.client import AzureMLClient
from workers import celery_app

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting up application...")
    
    # Initialize database
    Base.metadata.create_all(bind=engine)
    
    # Initialize Azure ML client
    app.state.azure_ml = AzureMLClient()
    
    # Initialize Celery
    celery_app.conf.update(broker_url=settings.CELERY_BROKER_URL)
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    # Cleanup connections

# Create FastAPI application
app = FastAPI(
    title="Anomaly Detection Platform API",
    description="AI-powered anomaly detection system for BETH dataset analysis",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure middleware
app.add_middleware(RateLimitMiddleware)
configure_cors(app)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.APP_ENV
    }

@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {
        "message": "Anomaly Detection Platform API",
        "documentation": "/api/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )