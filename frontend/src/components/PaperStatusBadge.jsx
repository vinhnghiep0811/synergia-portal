const STATUS_LABELS = {
  pending: "Pending",
  processed: "Processed",
  failed: "Failed",
};

const STATUS_BADGE_CLASS = {
  pending: "badge badge--pending",
  processed: "badge badge--processed",
  failed: "badge badge--failed",
};

export function PaperStatusBadge({ status }) {
  const label = STATUS_LABELS[status] ?? status;
  const className = STATUS_BADGE_CLASS[status] ?? "badge";
  return <span className={className}>{label}</span>;
}

