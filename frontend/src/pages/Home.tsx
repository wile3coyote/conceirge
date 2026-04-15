import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { del, post, get, ApiError } from "../api/client";
import type { LibraryItem, MovieSearchResult } from "../api/types";
import SearchBar from "../components/SearchBar";
import MovieCard from "../components/MovieCard";
import LibraryCard from "../components/LibraryCard";

export default function Home() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MovieSearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [addingTmdbId, setAddingTmdbId] = useState<number | null>(null);

  const { data: library = [] } = useQuery<LibraryItem[]>({
    queryKey: ["library"],
    queryFn: () => get<LibraryItem[]>("/library"),
    refetchInterval: 5000,
  });

  const libraryTmdbIds = new Set(library.map((item) => item.tmdb_id));

  const searchMutation = useMutation({
    mutationFn: (q: string) =>
      post<MovieSearchResult[]>("/movies/search", { query: q }),
    onSuccess: (data) => {
      setSearchResults(data);
      setSearchError(null);
    },
    onError: (err) => {
      setSearchResults([]);
      setSearchError(err instanceof ApiError ? err.detail : "Search failed");
    },
  });

  const addMutation = useMutation({
    mutationFn: (movie: MovieSearchResult) =>
      post<LibraryItem>("/library", {
        tmdb_id: movie.tmdb_id,
        title: movie.title,
        year: movie.year,
        overview: movie.overview,
        poster_url: movie.poster_url,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["library"] });
      setAddingTmdbId(null);
    },
    onError: () => {
      setAddingTmdbId(null);
    },
  });

  const retryMutation = useMutation({
    mutationFn: (id: number) => post<LibraryItem>(`/library/${id}/retry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => del(`/library/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library"] }),
  });

  const handleSearch = (q: string) => {
    setQuery(q);
    searchMutation.mutate(q);
  };

  const handleAdd = (movie: MovieSearchResult) => {
    setAddingTmdbId(movie.tmdb_id);
    addMutation.mutate(movie);
  };

  return (
    <div className="space-y-10">
      <section>
        <SearchBar onSearch={handleSearch} isLoading={searchMutation.isPending} />
        {searchError && (
          <p className="mt-3 text-red-400 text-sm">{searchError}</p>
        )}
        {searchResults.length > 0 && (
          <div className="mt-6">
            <h2 className="text-sm font-medium text-gray-400 mb-4">
              Results for &ldquo;{query}&rdquo;
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
              {searchResults.map((movie) => (
                <MovieCard
                  key={movie.tmdb_id}
                  movie={movie}
                  onAdd={handleAdd}
                  isAdding={
                    addingTmdbId === movie.tmdb_id && addMutation.isPending
                  }
                  alreadyInLibrary={libraryTmdbIds.has(movie.tmdb_id)}
                />
              ))}
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold text-white mb-4">Library</h2>
        {library.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No movies in your library yet. Search above to add one.
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {library.map((item) => (
              <LibraryCard
                key={item.id}
                item={item}
                onRetry={retryMutation.mutate}
                onDelete={deleteMutation.mutate}
                isRetrying={
                  retryMutation.isPending &&
                  retryMutation.variables === item.id
                }
                isDeleting={
                  deleteMutation.isPending &&
                  deleteMutation.variables === item.id
                }
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
