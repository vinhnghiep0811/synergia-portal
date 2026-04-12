class ActivityActorType:
    USER = "user"
    SYSTEM = "system"
    ADMIN = "admin"


class ActivityStatus:
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ActivityObjectType:
    PAPER_RECORD = "paper_record"
    CANONICAL_DOCUMENT = "canonical_document"
    EXTRACTION_RUN = "extraction_run"


class ActivityEventType:
    # paper lifecycle
    PAPER_UPLOADED = "paper_uploaded"
    PAPER_UPDATED = "paper_updated"
    PAPER_DELETED = "paper_deleted"
    PAPER_METADATA_EDITED = "paper_metadata_edited"
    PAPER_PUBLISHED = "paper_published"
    PAPER_UNPUBLISHED = "paper_unpublished"

    # parse pipeline
    PARSE_QUEUED = "parse_queued"
    PARSE_QUEUE_FAILED = "parse_queue_failed"
    PARSE_STARTED = "parse_started"
    PARSE_COMPLETED = "parse_completed"
    PARSE_FAILED = "parse_failed"
    PARSE_RETRIED = "parse_retried"

    # canonicalization / duplicate
    CANONICAL_CREATED = "canonical_created"
    CANONICAL_LINKED = "canonical_linked"
    DUPLICATE_DETECTED = "duplicate_detected"

    # semantic scholar enrichment
    SEMANTIC_SCHOLAR_QUEUED = "semantic_scholar_queued"
    SEMANTIC_SCHOLAR_STARTED = "semantic_scholar_started"
    SEMANTIC_SCHOLAR_MATCHED = "semantic_scholar_matched"
    SEMANTIC_SCHOLAR_UNMATCHED = "semantic_scholar_unmatched"
    SEMANTIC_SCHOLAR_FAILED = "semantic_scholar_failed"
    SEMANTIC_SCHOLAR_SKIPPED_CACHE_HIT = "semantic_scholar_skipped_cache_hit"
    # llm extraction
    LLM_EXTRACTION_QUEUED = "llm_extraction_queued"
    LLM_EXTRACTION_STARTED = "llm_extraction_started"
    LLM_EXTRACTION_COMPLETED = "llm_extraction_completed"
    LLM_EXTRACTION_FAILED = "llm_extraction_failed"
    LLM_EXTRACTION_SKIPPED_CACHE_HIT = "llm_extraction_skipped_cache_hit"

    # admin / system operations
    ADMIN_ALLOWLIST_UPDATED = "admin_allowlist_updated"
    ADMIN_SETTING_UPDATED = "admin_setting_updated"
    ADMIN_API_KEY_UPDATED = "admin_api_key_updated"