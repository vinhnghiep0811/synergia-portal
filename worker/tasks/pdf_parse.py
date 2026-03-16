import logging
from uuid import UUID

logger = logging.getLogger(__name__)


def pdf_parse(paper_id: str) -> None:
    try:
        paper_uuid = UUID(paper_id)
    except ValueError:
        logger.error(f"Invalid paper_id: {paper_id}")
        return

    logger.info(f"[pdf_parse] Start processing paper_id={paper_uuid}")

    logger.info(f"[pdf_parse] Finished skeleton run for paper_id={paper_uuid}")