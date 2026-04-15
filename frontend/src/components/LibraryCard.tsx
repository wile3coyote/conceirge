import type { LibraryItem } from "../api/types";
import StatusBadge from "./StatusBadge";

interface LibraryCardProps {
  item: LibraryItem;
  onRetry: (id: number) => void;
  onDelete: (id: number) => void;
  isRetrying: boolean;
  isDeleting: boolean;
}

export default function LibraryCard({
  item,
  onRetry,
  onDelete,
  isRetrying,
  isDeleting,
}: LibraryCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden flex flex-col">
      <div className="aspect-[2/3] bg-gray-700 relative">
        {item.poster_url ? (
          <img
            src={item.poster_url}
            alt={`${item.title} poster`}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
            No poster
          </div>
        )}
      </div>
      <div className="p-3 flex flex-col flex-1">
        <h3 className="font-semibold text-white text-sm leading-tight">
          {item.title}
        </h3>
        <p className="text-gray-400 text-xs mt-0.5">{item.year}</p>
        <div className="mt-2">
          <StatusBadge status={item.status} />
        </div>
        {item.fail_reason && (
          <p className="text-red-400 text-xs mt-1">{item.fail_reason}</p>
        )}
        {item.chosen_release_quality && (
          <p className="text-gray-500 text-xs mt-1">
            {item.chosen_release_quality}
            {item.chosen_release_size_gb != null &&
              ` · ${item.chosen_release_size_gb.toFixed(1)} GB`}
          </p>
        )}
        {item.status === "downloading" && item.download_progress != null && (
          <div className="mt-2">
            <div className="flex justify-between text-xs text-gray-400 mb-0.5">
              <span>Downloading</span>
              <span>{item.download_progress.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-1.5">
              <div
                className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${item.download_progress}%` }}
              />
            </div>
          </div>
        )}
        <div className="mt-3 flex gap-2">
          {item.status === "failed" && (
            <button
              onClick={() => onRetry(item.id)}
              disabled={isRetrying}
              className="flex-1 py-1.5 rounded text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 transition-colors"
            >
              {isRetrying ? "Retrying..." : "Retry"}
            </button>
          )}
          <button
            onClick={() => onDelete(item.id)}
            disabled={isDeleting}
            className="flex-1 py-1.5 rounded text-xs font-medium bg-gray-700 hover:bg-red-900 text-gray-300 hover:text-red-300 disabled:opacity-50 transition-colors"
          >
            {isDeleting ? "Removing..." : "Remove"}
          </button>
        </div>
      </div>
    </div>
  );
}
