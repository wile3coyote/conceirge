import type { Download } from "../api/types";
import StatusBadge from "./StatusBadge";

interface DownloadRowProps {
  download: Download;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function DownloadRow({ download }: DownloadRowProps) {
  return (
    <div className="flex items-center gap-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
      <div className="flex-1 min-w-0">
        <p className="font-medium text-white truncate">
          {download.movie_title}{" "}
          <span className="text-gray-400 font-normal text-sm">
            ({download.year})
          </span>
        </p>
        {download.chosen_release_title && (
          <p className="text-xs text-gray-500 mt-0.5 truncate">
            {download.chosen_release_title}
            {download.chosen_release_quality &&
              ` — ${download.chosen_release_quality}`}
            {download.chosen_release_size_gb !== null &&
              ` — ${download.chosen_release_size_gb.toFixed(1)} GB`}
          </p>
        )}
      </div>

      <div className="shrink-0">
        <StatusBadge status={download.status} />
      </div>

      <div className="shrink-0 text-right text-xs text-gray-500">
        <p>{formatDate(download.created_at)}</p>
        {download.completed_at && (
          <p className="mt-0.5">{formatDate(download.completed_at)}</p>
        )}
      </div>
    </div>
  );
}
