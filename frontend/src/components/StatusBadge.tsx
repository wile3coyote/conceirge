import type { DownloadStatus } from "../api/types";

const STATUS_STYLES: Record<DownloadStatus, string> = {
  pending: "bg-yellow-500/20 text-yellow-300",
  searching: "bg-yellow-500/20 text-yellow-300",
  grabbed: "bg-blue-500/20 text-blue-300",
  complete: "bg-green-500/20 text-green-300",
  failed: "bg-red-500/20 text-red-300",
};

interface StatusBadgeProps {
  status: DownloadStatus;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}
