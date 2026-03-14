import os
from dotenv import load_dotenv

load_dotenv()
def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}

# Environment: dev | prod
ENV = get_env("ENV", "dev")

# =========================
# CORS
# =========================
CORS_ORIGINS = [
    o.strip() for o in get_env(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# =========================
# DATABASE
# =========================
DB_HOST = get_env("DB_HOST", "127.0.0.1")
DB_PORT = get_env("DB_PORT", "5432")
DB_NAME = get_env("DB_NAME", "synergia_portal")
DB_USER = get_env("DB_USER", "postgres")
DB_PASSWORD = get_env("DB_PASSWORD", "postgres")


DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# =========================
# Storage
# =========================
STORAGE_PATH = get_env("STORAGE_PATH", "./storage")

# =========================
# STORAGE - MinIO
# =========================
MINIO_ENDPOINT = get_env("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = get_env("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = get_env("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = get_env("MINIO_BUCKET", "papers")
MINIO_SECURE = get_env_bool("MINIO_SECURE", False)

# =========================
# Upload constraints
# =========================
MAX_UPLOAD_SIZE_MB = get_env_int("MAX_UPLOAD_SIZE_MB", 20)
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# =========================
# Auth - Google OAuth2
# =========================
GOOGLE_CLIENT_ID = get_env("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = get_env("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = get_env(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:8000/api/auth/google/callback",
)
ALLOWED_EMAIL_DOMAIN = get_env("ALLOWED_EMAIL_DOMAIN", "hcmut.edu.vn")

# =========================
# Auth - JWT
# =========================
JWT_SECRET_KEY = get_env("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = get_env("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = get_env_int("JWT_EXPIRE_MINUTES", 60 * 24 * 7)  # 7 ngày