"""Environment-driven application configuration."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "local-development-key-change-me")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "dataviz_dash")
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024
    MAX_DATASET_ROWS = int(os.getenv("MAX_DATASET_ROWS", "50000"))
    CHART_ROW_LIMIT = int(os.getenv("CHART_ROW_LIMIT", "50000"))
    FREE_UPLOAD_MB = int(os.getenv("FREE_UPLOAD_MB", "10"))
    FREE_DATASET_ROWS = int(os.getenv("FREE_DATASET_ROWS", "10000"))
    FREE_DATASET_LIMIT = int(os.getenv("FREE_DATASET_LIMIT", "3"))
    FREE_DASHBOARD_LIMIT = int(os.getenv("FREE_DASHBOARD_LIMIT", "2"))
    FREE_CHART_LIMIT = int(os.getenv("FREE_CHART_LIMIT", "4"))
    FREE_CHART_ROW_LIMIT = int(os.getenv("FREE_CHART_ROW_LIMIT", "10000"))
    PRO_DATASET_LIMIT = int(os.getenv("PRO_DATASET_LIMIT", "25"))
    PRO_DASHBOARD_LIMIT = int(os.getenv("PRO_DASHBOARD_LIMIT", "25"))
    PRO_CHART_LIMIT = int(os.getenv("PRO_CHART_LIMIT", "8"))
    JSON_SORT_KEYS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30
