export type LibraryStatus =
  | "searching"
  | "grabbing"
  | "downloading"
  | "downloaded"
  | "in_library"
  | "failed";

export interface LibraryItem {
  id: number;
  tmdb_id: number;
  radarr_movie_id: number | null;
  title: string;
  year: number;
  overview: string | null;
  poster_url: string | null;
  status: LibraryStatus;
  fail_reason: string | null;
  chosen_release_title: string | null;
  chosen_release_size_gb: number | null;
  chosen_release_quality: string | null;
  download_id: string | null;
  download_progress: number | null;
  created_at: string;
  updated_at: string;
}

export interface AppSettings {
  max_size_gb: number;
  preferred_quality: string;
  avoid_keywords: string[];
  updated_at: string;
}

export interface MovieSearchResult {
  tmdb_id: number;
  title: string;
  year: number;
  overview: string | null;
  poster_url: string | null;
}
