import type { MovieSearchResult } from "../api/types";

interface MovieCardProps {
  movie: MovieSearchResult;
  onAdd: (movie: MovieSearchResult) => void;
  isAdding: boolean;
  alreadyInLibrary: boolean;
}

export default function MovieCard({
  movie,
  onAdd,
  isAdding,
  alreadyInLibrary,
}: MovieCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden flex flex-col">
      <div className="aspect-[2/3] bg-gray-700 relative">
        {movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt={`${movie.title} poster`}
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
          {movie.title}
        </h3>
        <p className="text-gray-400 text-xs mt-0.5">{movie.year}</p>
        {movie.overview && (
          <p className="text-gray-500 text-xs mt-1 line-clamp-2 flex-1">
            {movie.overview}
          </p>
        )}
        <button
          onClick={() => onAdd(movie)}
          disabled={isAdding || alreadyInLibrary}
          className={`mt-3 w-full py-1.5 rounded text-xs font-medium transition-colors ${
            alreadyInLibrary
              ? "bg-gray-600 text-gray-400 cursor-not-allowed"
              : isAdding
                ? "bg-indigo-700 text-indigo-300 cursor-wait"
                : "bg-indigo-600 hover:bg-indigo-500 text-white"
          }`}
        >
          {alreadyInLibrary ? "In Library" : isAdding ? "Adding..." : "Add to Library"}
        </button>
      </div>
    </div>
  );
}
