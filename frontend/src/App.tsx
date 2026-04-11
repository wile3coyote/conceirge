import { NavLink, Route, Routes } from "react-router-dom";
import Search from "./pages/Search";
import Downloads from "./pages/Downloads";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <nav className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-5xl mx-auto px-4 py-3 flex gap-6 items-center">
          <span className="font-bold text-lg tracking-tight text-white mr-4">
            Concierge
          </span>
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive
                ? "text-white font-semibold border-b-2 border-indigo-400 pb-0.5"
                : "text-gray-400 hover:text-white transition-colors"
            }
          >
            Search
          </NavLink>
          <NavLink
            to="/downloads"
            className={({ isActive }) =>
              isActive
                ? "text-white font-semibold border-b-2 border-indigo-400 pb-0.5"
                : "text-gray-400 hover:text-white transition-colors"
            }
          >
            Downloads
          </NavLink>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Search />} />
          <Route path="/downloads" element={<Downloads />} />
        </Routes>
      </main>
    </div>
  );
}
