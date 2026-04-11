export type DownloadStatus =
  | "pending"
  | "searching"
  | "grabbed"
  | "complete"
  | "failed";

export interface Download {
  id: number;
  radarr_movie_id: number;
  movie_title: string;
  year: number;
  status: DownloadStatus;
  chosen_release_title: string | null;
  chosen_release_size_gb: number | null;
  chosen_release_quality: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ScoredRelease {
  title: string;
  size_gb: number;
  quality: string;
  score: number;
  rejected: boolean;
  reject_reason: string | null;
  radarr_guid: string;
}
