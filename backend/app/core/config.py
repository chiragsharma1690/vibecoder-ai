import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Security
SECRET_KEY = os.environ.get("VIBECODER_SECRET_KEY", "fallback-secret-if-missing")

# Application Settings
FRONTEND_CORS_ORIGIN = os.environ.get("FRONTEND_CORS_ORIGIN", "http://localhost:5173")

# LLM Constants
DEFAULT_LLM_MODEL = os.environ.get("DEFAULT_LLM_MODEL", "qwen2.5-coder:7b")
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", 180))
MAX_CI_ATTEMPTS = int(os.environ.get("MAX_CI_ATTEMPTS", 2))

# Database Constants
DB_NAME = os.environ.get("DB_NAME", "vibecoder.db")
ENCRYPTION_KEY = os.environ.get("VIBECODER_ENCRYPTION_KEY")

# Webhook URLs for automated PR handoffs
REVIEWER_WEBHOOK_URL = os.environ.get("REVIEWER_WEBHOOK_URL", "http://localhost:8000/api/webhooks/reviewer")
QA_WEBHOOK_URL = os.environ.get("QA_WEBHOOK_URL", "http://localhost:8000/api/webhooks/qa")