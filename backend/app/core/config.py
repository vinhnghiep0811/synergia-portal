import os
from dotenv import load_dotenv

load_dotenv()
def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

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