# Mak-sMen - Anomaly Detection Platform

AI-powered anomaly detection system for BETH dataset analysis using FastAPI and modern ML techniques.

## 🚀 Quick Start

### Prerequisites

- Python 3.13+ 
- Git
- macOS/Linux/Windows

### 🔧 Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/WhiteHatHud/Mak-sMen.git
   cd Mak-sMen
   ```

2. **Navigate to backend directory**
   ```bash
   cd backend
   ```

3. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file with your configuration (optional for development)
   ```

6. **Start the development server**
   ```bash
   uvicorn main:app --reload --port 8001
   ```

7. **Access the API**
   - **API Documentation**: http://127.0.0.1:8001/api/docs
   - **Alternative Docs**: http://127.0.0.1:8001/api/redoc
   - **Root Endpoint**: http://127.0.0.1:8001/

## 📁 Project Structure

```
Mak-sMen/
├── backend/
│   ├── api/
│   │   ├── middleware/     # CORS, Rate limiting, Auth
│   │   ├── routes/         # API endpoints
│   │   └── validators/     # Request validation
│   ├── database/
│   │   ├── migrations/     # Database migrations
│   │   └── connection.py   # DB connection setup
│   ├── models/             # Data models
│   ├── services/
│   │   ├── anomaly_detection/  # ML anomaly detection
│   │   ├── azure_ml/       # Azure ML integration
│   │   ├── llm/            # LLM services
│   │   └── storage/        # File storage
│   ├── workers/            # Background tasks (Celery)
│   ├── tests/              # Test files
│   ├── utils/              # Helper utilities
│   ├── main.py             # FastAPI application entry point
│   ├── config.py           # Configuration settings
│   ├── requirements.txt    # Python dependencies
│   └── .env                # Environment variables
└── README.md              # This file
```

## 🛠️ Development

### Running Tests
```bash
cd backend
pytest
```

### Code Formatting
```bash
black .
flake8 .
```

### Type Checking
```bash
mypy .
```

## 📋 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint with API info |
| `/health` | GET | Health check |
| `/api/projects` | GET, POST | Project management |
| `/api/files` | GET, POST | File upload and management |
| `/api/analysis` | GET, POST | Anomaly detection analysis |
| `/api/reports` | GET, POST | Report generation |
| `/api/webhooks` | POST | Webhook endpoints |

## ⚙️ Configuration

### Environment Variables

Key environment variables (all optional for development):

```bash
# Application
APP_NAME=Anomaly Detection Platform
APP_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=sqlite:///./app.db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Azure Services (optional)
AZURE_BLOB_CONNECTION_STRING=
AZURE_ML_SUBSCRIPTION_ID=
AZURE_ML_RESOURCE_GROUP=
AZURE_ML_WORKSPACE_NAME=

# OpenAI (optional)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4
```

### Development Mode

For development, the application runs with:
- ✅ SQLite database (no PostgreSQL required)
- ✅ Rate limiting disabled (no Redis required)
- ✅ Hot reload enabled
- ✅ Debug mode enabled
- ✅ CORS configured for local development

## 🔍 Features

### Core Features
- **Anomaly Detection**: ML-powered anomaly detection for BETH datasets
- **File Processing**: Support for CSV, JSON, Parquet, Excel, and PDF files
- **Report Generation**: Automated report generation with LLM explanations
- **Real-time Analysis**: Background processing with Celery workers
- **API Documentation**: Interactive Swagger UI and ReDoc

### Integrations
- **Azure ML**: Machine learning model deployment and management
- **Azure Storage**: Blob storage for file management
- **OpenAI**: LLM-powered explanations and insights
- **Redis**: Caching and background job queue
- **PostgreSQL**: Production database support

## 🚀 Deployment

### Docker
```bash
cd backend
docker build -t anomaly-detection-api .
docker run -p 8000:8000 anomaly-detection-api
```

### Production
For production deployment, ensure you:
1. Set `DEBUG=false` in environment
2. Configure proper database (PostgreSQL)
3. Set up Redis for caching and background jobs
4. Configure Azure services
5. Set strong `SECRET_KEY`
6. Enable HTTPS

## 🧪 Testing

Run the test suite:
```bash
cd backend
pytest tests/ -v
```

### Test Coverage
```bash
pytest --cov=. tests/
```

## 📖 Documentation

- **API Docs**: Available at `/api/docs` when server is running
- **Code Documentation**: See inline docstrings and type hints
- **Architecture**: See `docs/` folder for detailed architecture documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Troubleshooting

### Common Issues

**Server won't start:**
- Ensure virtual environment is activated
- Check if port is already in use
- Verify all dependencies are installed

**Import errors:**
- Make sure you're in the `backend` directory
- Activate virtual environment: `source venv/bin/activate`

**Database errors:**
- For development, SQLite is used by default (no setup required)
- Check DATABASE_URL in `.env` file

**Redis connection errors:**
- Rate limiting is disabled in development mode
- Redis is only required for production deployment

### Getting Help

- Check the [API documentation](http://127.0.0.1:8001/api/docs) when server is running
- Review logs in `backend/logs/app.log`
- Open an issue on GitHub for bug reports

## 🔄 Recent Updates

- ✅ FastAPI backend setup complete
- ✅ Virtual environment configured
- ✅ Development server running on port 8001
- ✅ API documentation available
- ✅ Redis dependency made optional for development

---

**Happy Coding! 🎉**

For more information, visit the [API documentation](http://127.0.0.1:8001/api/docs) when the server is running.