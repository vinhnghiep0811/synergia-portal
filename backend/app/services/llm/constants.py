import os

PROMPT_VERSION = "v4"

SECTION_CANDIDATES = [
    "abstract",
    "introduction",
    "background",
    "related work",
    "method",
    "approach",
    "model",
    "experiment",
    "experiments",
    "evaluation",
    "results",
    "discussion",
    "limitation",
    "limitations",
    "conclusion",
]

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


MAX_INPUT_CHARS = max(2000, _env_int("LLM_MAX_INPUT_CHARS", 12000))
MAX_SECTION_CHARS = 6000
MAX_EVIDENCE_SNIPPET_CHARS = 500
