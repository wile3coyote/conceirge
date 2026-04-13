import type { LibraryStatus } from "../api/types";

const STATUS_STYLES: Record<LibraryStatus, string> = {
  searching: "bg-yellow-500/20 text-yellow-300",
  grabbing: "bg-blue-500/20 text-blue-300",
  downloading: "bg-indigo-500/20 text-indigo-300",
  downloaded: "bg-teal-500/20 text-teal-300",
  in_library: "bg-green-500/20 text-green-300",
  failed: "bg-red-500/20 text-red-300",
};

const STATUS_LABELS: Record<LibraryStatus, string> = {
  searching: "Searching",
  grabbing: "Grabbing",
  downloading: "Downloading",
  downloaded: "Downloaded",
  in_library: "In Library",
  failed: "Failed",
};

interface StatusBadgeProps {
  status: LibraryStatus;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
