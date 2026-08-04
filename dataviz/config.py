"""Environment-driven application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "local-development-key-change-me")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "dataviz_dash")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
    MAX_DATASET_ROWS = int(os.getenv("MAX_DATASET_ROWS", "10000"))
    CHART_ROW_LIMIT = int(os.getenv("CHART_ROW_LIMIT", "10000"))
    JSON_SORT_KEYS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
