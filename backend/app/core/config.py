import os

def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

ENV = get_env("ENV", "dev")

# Comma-separated list
CORS_ORIGINS = [
    o.strip() for o in get_env(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]