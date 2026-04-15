import Home from "./pages/Home";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-5xl mx-auto px-4 py-3">
          <span className="font-bold text-lg tracking-tight text-white">
            Concierge
          </span>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Home />
      </main>
    </div>
  );
}
