import type { ScoredRelease } from "../api/types";

const QUALITY_STYLES: Record<string, string> = {
  "2160p": "bg-purple-500/20 text-purple-300",
  "1080p": "bg-blue-500/20 text-blue-300",
};

function qualityStyle(quality: string): string {
  return QUALITY_STYLES[quality] ?? "bg-gray-500/20 text-gray-400";
}

interface ReleaseCardProps {
  release: ScoredRelease;
  selected?: boolean;
  onSelect?: () => void;
}

export default function ReleaseCard({
  release,
  selected = false,
  onSelect,
}: ReleaseCardProps) {
  return (
    <div
      onClick={onSelect}
      className={`p-4 rounded-lg border transition-colors cursor-pointer ${
        selected
          ? "border-indigo-500 bg-indigo-500/10"
          : "border-gray-700 bg-gray-800 hover:border-gray-600"
      } ${release.rejected ? "opacity-50" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-200 leading-snug flex-1 min-w-0 truncate">
          {release.title}
        </p>
        <span
          className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${qualityStyle(release.quality)}`}
        >
          {release.quality}
        </span>
      </div>

      <div className="mt-2 flex items-center gap-4 text-xs text-gray-400">
        <span>{release.size_gb.toFixed(1)} GB</span>
        <span>Score: {release.score}</span>
        {release.rejected && release.reject_reason && (
          <span className="text-red-400">{release.reject_reason}</span>
        )}
      </div>
    </div>
  );
}
