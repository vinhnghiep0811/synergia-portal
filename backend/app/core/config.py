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
# GOOGLE
# =========================

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

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
# STORAGE - S3 compatible (RustFS)
# =========================
S3_ENDPOINT = get_env("S3_ENDPOINT", "rustfs:9000")
S3_ACCESS_KEY = get_env("S3_ACCESS_KEY", "rustfsadmin")
S3_SECRET_KEY = get_env("S3_SECRET_KEY", "rustfsadmin")
S3_BUCKET = get_env("S3_BUCKET", "papers")
S3_SECURE = get_env_bool("S3_SECURE", False)

S3_PUBLIC_ENDPOINT = get_env("S3_PUBLIC_ENDPOINT", "localhost:9000")
S3_PUBLIC_SECURE = get_env_bool("S3_PUBLIC_SECURE", False)

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

ADMIN_EMAILS = [
    email.strip().lower()
    for email in get_env("ADMIN_EMAILS", "").split(",")
    if email.strip()
]

# Frontend callback URL (override in production via env)
FRONTEND_AUTH_CALLBACK_URL = get_env("FRONTEND_AUTH_CALLBACK_URL", "http://localhost:5173/auth/callback")

# =========================
# Auth - JWT
# =========================
JWT_SECRET_KEY = get_env("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError(
        "Missing required environment variable JWT_SECRET_KEY. Set a secure random value before starting the app."
    )
JWT_ALGORITHM = get_env("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = get_env_int("JWT_EXPIRE_MINUTES", 60 * 24 * 7)  # 7 ngày

# =========================
# Queue - Redis / RQ
# =========================
REDIS_HOST = get_env("REDIS_HOST", "127.0.0.1")
REDIS_PORT = get_env_int("REDIS_PORT", 6379)
REDIS_DB = get_env_int("REDIS_DB", 0)
REDIS_URL = get_env("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

RQ_PARSE_QUEUE = get_env("RQ_PARSE_QUEUE", "parse_queue")
REFRESH_TOKEN_SECRET_KEY  = get_env("REFRESH_TOKEN_SECRET_KEY", "change-refresh-secret")
REFRESH_TOKEN_EXPIRE_DAYS = get_env_int("REFRESH_TOKEN_EXPIRE_DAYS", 30)

# =========================
# LLM - Gemini (Week 5)
# =========================
LLM_PROVIDER = get_env("LLM_PROVIDER", "gemini")

GEMINI_API_KEY = get_env("GEMINI_API_KEY", "")
GEMINI_MODEL = get_env("GEMINI_MODEL", "gemini-2.5-pro")

GEMINI_TEMPERATURE = float(get_env("GEMINI_TEMPERATURE", "0"))
GEMINI_MAX_OUTPUT_TOKENS = get_env_int("GEMINI_MAX_OUTPUT_TOKENS", 4096)

LLM_TIMEOUT_SECONDS = get_env_int("LLM_TIMEOUT_SECONDS", 60)