const STATUS_META = {
  pending: { label: "Pending", className: "badge badge--pending" },
  parse_queued: { label: "Queued", className: "badge badge--pending" },
  canonicalized: { label: "Canonicalized", className: "badge badge--pending" },
  processing: { label: "Processing", className: "badge badge--pending" },
  parsed: { label: "Parsed", className: "badge badge--pending" },
  enriched: { label: "Enriched", className: "badge badge--pending" },
  llm_extracting: { label: "LLM Extracting", className: "badge badge--pending" },
  citation_scoring: { label: "Citation Scoring", className: "badge badge--pending" },
  citation_scored: { label: "Citation Scored", className: "badge badge--processed" },
  processed: { label: "Processed", className: "badge badge--processed" },
  completed: { label: "Completed", className: "badge badge--processed" },
  duplicate_detected: { label: "Duplicate", className: "badge badge--processed" },
  failed: { label: "Failed", className: "badge badge--failed" },
};

function formatFallbackStatus(status) {
  if (!status) return "Unknown";
  return String(status)
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function PaperStatusBadge({ status }) {
  const meta = STATUS_META[status];
  const label = meta?.label ?? formatFallbackStatus(status);
  const className = meta?.className ?? "badge badge--pending";
  return <span className={className}>{label}</span>;
}

