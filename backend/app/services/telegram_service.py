from __future__ import annotations

import logging

import httpx

from app.core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.models.canonical_document import CanonicalDocument
from app.models.paper_record import PaperRecord
from app.models.publish_version import PublishVersion

logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self) -> None:
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID

    def send_publish_notification(
        self,
        publish_version: PublishVersion,
        canonical: CanonicalDocument | None,
        paper: PaperRecord,
    ) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("[TELEGRAM] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID, skip notify")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        message = self._build_publish_message(publish_version, canonical, paper)

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }

        try:
            response = httpx.post(url, json=payload, timeout=15)
            if response.status_code != 200:
                logger.error(
                    "[TELEGRAM] sendMessage failed status=%s body=%s",
                    response.status_code,
                    response.text[:300],
                )
                return False

            body = response.json()
            if not body.get("ok"):
                logger.error("[TELEGRAM] sendMessage returned ok=false body=%s", body)
                return False

            logger.info(
                "[TELEGRAM] Publish notify sent publish_version_id=%s paper_id=%s",
                publish_version.id,
                paper.id,
            )
            return True
        except Exception as error:
            logger.exception("[TELEGRAM] sendMessage unexpected error: %s", error)
            return False

    def _build_publish_message(
        self,
        publish_version: PublishVersion,
        canonical: CanonicalDocument | None,
        paper: PaperRecord,
    ) -> str:
        title = (
            publish_version.title_override
            or (canonical.title if canonical else None)
            or (canonical.title_candidate if canonical else None)
            or paper.detected_title
            or paper.original_filename
        )

        venue = publish_version.venue_override or (canonical.venue if canonical else None) or "-"
        year = publish_version.year_override or (canonical.publication_year if canonical else None) or "-"

        return "\n".join(
            [
                "New paper published in Synergia Portal",
                f"Title: {title}",
                f"Venue: {venue}",
                f"Year: {year}",
                f"Paper ID: {paper.id}",
                f"Canonical ID: {paper.canonical_document_id}",
                f"Publish Version: v{publish_version.version_number}",
                f"Published by: {publish_version.published_by or '-'}",
            ]
        )
