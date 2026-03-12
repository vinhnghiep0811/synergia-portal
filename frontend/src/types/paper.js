/**
 * @typedef {Object} PaperUploadResponse
 * @property {string} id
 * @property {string} original_filename
 * @property {string} storage_path
 * @property {string} mime_type
 * @property {number} file_size_bytes
 * @property {string} file_hash_sha256
 * @property {string} status
 * @property {string} upload_source
 * @property {string} created_at
 */

/**
 * @typedef {Object} PaperListItemResponse
 * @property {string} id
 * @property {string} original_filename
 * @property {string} status
 * @property {string} mime_type
 * @property {number} file_size_bytes
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * @typedef {Object} PaperDetailResponse
 * @property {string} id
 * @property {string | null} canonical_document_id
 * @property {string | null} uploader_id
 * @property {string} original_filename
 * @property {string} storage_path
 * @property {string} mime_type
 * @property {number} file_size_bytes
 * @property {string} file_hash_sha256
 * @property {string} upload_source
 * @property {string} status
 * @property {string | null} parse_status
 * @property {string | null} parse_error
 * @property {string | null} extracted_text_preview
 * @property {string | null} detected_doi
 * @property {string | null} detected_title
 * @property {string} created_at
 * @property {string} updated_at
 */

export const PAPER_STATUS = {
  PENDING: "pending",
  PROCESSED: "processed",
  FAILED: "failed",
};